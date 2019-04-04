from beekeeper import VERSION
from beekeeper.export import Exporter

import sys, os, traceback
import click
from click import ClickException
from pathlib import Path
import logging
import json
from datetime import date
from yaml import load, CLoader as Loader
import dateutil.parser
from pathos.multiprocessing import Pool
import re
import requests

logging.basicConfig(
    level=logging.WARNING,
    format=' %(asctime)s [%(levelname)-7s] %(message)s',
    datefmt='%I:%M:%S %p')
logger = logging.getLogger('beekeeper')

logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

def get_folder(base_directory, ticket):
    id = ticket['id']
    created = dateutil.parser.parse(ticket['created_at'])

    year = base_directory.joinpath(created.strftime('%Y'))
    month = year.joinpath(created.strftime('%Y-%m'))
    day = month.joinpath(created.strftime('%Y-%m-%d'))
    id = day.joinpath(str(id))

    id.mkdir(parents=True, exist_ok=True)

    return id


def save_ticket(base_directory, ticket):
    destination_dir = get_folder(base_directory, ticket)
    ticket_file = destination_dir.joinpath('ticket.json')

    with ticket_file.open('w') as writer:
        writer.write(json.dumps(ticket))

def save_replies(exporter, ticket_file):
    parent = ticket_file.parent
    replies_file = parent.joinpath('replies.json')
    id = parent.name
    # Get the replies for this ticket
    replies = exporter.get_replies(id)
    # Store the result
    with replies_file.open('w') as writer:
        content = json.dumps(replies)
        writer.write(content)

def save_comments(exporter, ticket_file):
    parent = ticket_file.parent
    comments_file = parent.joinpath('comments.json')
    id = parent.name
    # Get the comments for this ticket
    comments = exporter.get_comments(id)
    # Store the result
    with comments_file.open('w') as writer:
        content = json.dumps(comments)
        writer.write(content)

def save_attachments(token, timeout, ticket_file):
    parent = ticket_file.parent
    attachments_folder = parent.joinpath('attachments')

    with ticket_file.open('r') as reader:
        ticket = json.loads(reader.read())

    attachments = ticket['content']['attachments']

    if len(attachments) > 0:
        logger.debug('{} attachments to download'.format(len(attachments)))
        attachments_folder.mkdir(exist_ok=True)
        for attachment in attachments:
            url = attachment['url']['original'] + '?auth_token={0}'.format(token)
            r = requests.get(url, timeout=timeout)
            fname = attachment['filename']
            attachment_file = attachments_folder.joinpath(fname)
            with attachment_file.open('wb') as writer:
                writer.write(r.content)

@click.group(context_settings=CONTEXT_SETTINGS)
@click.option('-l', '--loglevel', type=click.Choice(['error', 'warn', 'info', 'debug']), default='warn')
@click.option('-c', '--config', type=click.Path(exists=True), default=os.path.realpath('config.yaml'))
@click.version_option(VERSION, '--version', '-v')
@click.pass_context
def cli(ctx, loglevel, config):
    """
    This command line tool helps you export your SupportBee account data.
    """
    if loglevel == 'error':
        logger.setLevel(logging.ERROR)
    elif loglevel == 'warn':
        logger.setLevel(logging.WARNING)
    elif loglevel == 'info':
        logger.setLevel(logging.INFO)
    elif loglevel == 'debug':
        logger.setLevel(logging.DEBUG)
    else:
        ClickException('no log level')

    if ctx.invoked_subcommand is None:
        click.echo('I was invoked without subcommand')
    else:
        # ensure that ctx.obj exists and is a dict (in case `cli()` is called
        # by means other than the `if` block below
        ctx.ensure_object(dict)

        config_file = Path(config)
        with config_file.open('r') as config_reader:
            config = load(config_reader.read(), Loader=Loader)['SupportBee']

        ctx.obj['exporter'] = Exporter(config)



@cli.command(help="Exports the users")
@click.pass_context
def users(ctx):
    obj = ctx.obj['exporter']
    try:
        users = obj.get_users()
        click.echo(json.dumps(users))
    except Exception as e:
        click.secho(str(e), fg='red')
        ctx.abort()


@cli.command(help="Exports the labels")
@click.pass_context
def labels(ctx):
    obj = ctx.obj['exporter']
    try:
        labels = obj.get_labels()
        click.echo(json.dumps(labels))
    except Exception as e:
        click.secho(str(e), fg='red')
        ctx.abort()

@cli.command(help="Exports the teams")
@click.pass_context
def teams(ctx):
    obj = ctx.obj['exporter']
    try:
        teams = obj.get_teams()
        click.echo(json.dumps(teams))
    except Exception as e:
        click.secho(str(e), fg='red')
        ctx.abort()

@cli.command(help="Exports the snippets")
@click.pass_context
def snippets(ctx):
    obj = ctx.obj['exporter']
    try:
        snippets = obj.get_snippets()
        click.echo(json.dumps(snippets))
    except Exception as e:
        click.secho(str(e), fg='red')
        ctx.abort()

@cli.command(help="Exports the forwarding addresses")
@click.pass_context
def emails(ctx):
    obj = ctx.obj['exporter']
    try:
        emails = obj.get_emails()
        click.echo(json.dumps(emails))
    except Exception as e:
        click.secho(str(e), fg='red')
        ctx.abort()

@cli.command(help="Exports all tickets in a folder structure")
@click.pass_context
def export_tickets(ctx):
    obj = ctx.obj['exporter']

    EXPORT_FOLDER = Path(obj.get_config()['export_folder'])
    # Create the base folder if it does not exist
    EXPORT_FOLDER.mkdir(parents=True, exist_ok=True)

    for result in obj.get_tickets(per_page=100):
        tickets = result.data
        print('{}/{}/{}'.format(result.page, result.total_pages, len(tickets)))
        for ticket in tickets:
            save_ticket(EXPORT_FOLDER, ticket)


@cli.command(help="Exports all replies from the tickets stored")
@click.pass_context
def export_replies(ctx):
    obj = ctx.obj['exporter']

    EXPORT_FOLDER = Path(obj.get_config()['export_folder'])
    PROCS = obj.get_config()['download_threads']

    # Get the current tickets
    tickets = list(EXPORT_FOLDER.joinpath('tickets').glob('**/*.json'))

    def save(ticket):
        save_replies(obj, ticket)

    with Pool(PROCS) as p:
        logger.info('Starting the download...')
        p.map(save, tickets)


@cli.command(help="Exports all comments from the tickets stored")
@click.pass_context
def export_comments(ctx):
    obj = ctx.obj['exporter']

    EXPORT_FOLDER = Path(obj.get_config()['export_folder'])
    PROCS = obj.get_config()['download_threads']

    # Get the current tickets
    tickets = list(EXPORT_FOLDER.joinpath('tickets').glob('**/ticket.json'))

    def save(ticket):
        save_comments(obj, ticket)

    with Pool(PROCS) as p:
        logger.info('Starting the download...')
        p.map(save, tickets)


@cli.command(help="Exports all attachments from the tickets stored")
@click.pass_context
def export_attachments(ctx):
    obj = ctx.obj['exporter']
    config = obj.get_config()
    EXPORT_FOLDER = Path(config['export_folder'])
    PROCS = config['download_threads']
    TOKEN = config['token']
    TIMEOUT = config['timeout']

    # Get the current tickets
    logger.debug('Getting the list of ticket files')
    tickets = list(EXPORT_FOLDER.joinpath('tickets').glob('**/ticket.json'))
    
    # Enrich the function with config data
    def save(ticket):
        save_attachments(TOKEN, TIMEOUT, ticket)

    with Pool(PROCS) as p:
        logger.info('Starting the download...')
        p.map(save, tickets)


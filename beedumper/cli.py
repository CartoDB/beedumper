from beedumper import VERSION
from beedumper.export import Exporter

import sys
import os
import traceback
import click
from click import ClickException
from pathlib import Path
import logging
import json
from datetime import date
from yaml import load, CLoader as Loader
from pathos.multiprocessing import ProcessPool as Pool
import re
import requests

from datetime import datetime
import dateutil.parser
import pytz

logging.basicConfig(
    level=logging.WARNING,
    format=' %(asctime)s [%(levelname)-7s] %(message)s',
    datefmt='%I:%M:%S %p')
logger = logging.getLogger('beedumper')

logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
TICKETS_PAGE = 100

RESULTS_DOWNLOAD = 1
RESULTS_SKIPPED = 2
RESULTS_OLD = 3

class DownloadFiles(object):
    __slots__ = 'downloaded', 'skipped',

    def __init__(self):
        self.downloaded = 0
        self.skipped = 0

    def add_downloaded(self):
        self.downloaded += 1

    def add_skippped(self):
        self.skipped +=1

def get_folder_old(base_directory, ticket):
    id = ticket['id']
    created = dateutil.parser.parse(ticket['created_at'])

    year = base_directory.joinpath(created.strftime('%Y'))
    month = year.joinpath(created.strftime('%Y-%m'))
    day = month.joinpath(created.strftime('%Y-%m-%d'))
    id = day.joinpath(str(id))

    id.mkdir(parents=True, exist_ok=True)

    return id

def get_folder(base_directory, ticket):
    id = int(ticket['id'])
    parent = base_directory.joinpath('tickets').joinpath(str(id % 99).zfill(2))
    id_folder = parent.joinpath(str(id))
    id_folder.mkdir(parents=True, exist_ok=True)

    return id_folder


def save_ticket(base_directory, ticket):
    destination_dir = get_folder(base_directory, ticket)
    ticket_file = destination_dir.joinpath('ticket.json')

    with ticket_file.open('w') as writer:
        writer.write(json.dumps(ticket))

def check_ticket_activity(ticket_obj, since_date):
    if 'last_activity_at' in ticket_obj and ticket_obj['last_activity_at'] != None:
        last_activity = dateutil.parser.parse(ticket_obj['last_activity_at'])
    else:
        last_activity = pytz.utc.localize(datetime.now())

    return last_activity > since_date

def save_replies(exporter, ticket_file, since_date, force):
    try:
        with ticket_file.open('r') as reader:
            ticket_obj = json.loads(reader.read())

        if check_ticket_activity(ticket_obj, since_date):
            parent = ticket_file.parent
            replies_file = parent.joinpath('replies.json')
            if force or not replies_file.exists():
                id = parent.name
                logger.debug('Saving replies for ticket {}'.format(id))
                # Get the replies for this ticket
                replies = exporter.get_replies(id)
                # Store the result
                with replies_file.open('w') as writer:
                    content = json.dumps(replies)
                    writer.write(content)
                    return RESULTS_DOWNLOAD
            else:
                logger.debug('Skipping download reply {}'.format(parent.name))
                return RESULTS_SKIPPED
        else:
            return RESULTS_OLD
    except Exception as e:
        logger.error(e)

def save_comments(exporter, ticket_file, since_date, force):
    try:
        with ticket_file.open('r') as reader:
            ticket_obj = json.loads(reader.read())
            
        if check_ticket_activity(ticket_obj, since_date):
            parent = ticket_file.parent
            comments_file = parent.joinpath('comments.json')
            id = parent.name
            if force or not comments_file.exists():
                logger.debug('Saving comments for ticket {}'.format(id))
                # Get the comments for this ticket
                comments = exporter.get_comments(id)
                # Store the result
                with comments_file.open('w') as writer:
                    content = json.dumps(comments)
                    writer.write(content)
                    return RESULTS_DOWNLOAD
            else:
                logger.debug('Skipping comments for ticket {}...'.format(id))
                return RESULTS_SKIPPED
        else:
            return RESULTS_OLD
    except Exception as e:
        logger.error('Error when processing ticket {}\r\n{}'.format(ticket_file.parent,str(e)))

def save_attachments(token, timeout, ticket_file, since_date, force=False):
    with ticket_file.open('r') as reader:
        ticket_obj = json.loads(reader.read())
    
    results = DownloadFiles()
        
    if check_ticket_activity(ticket_obj, since_date):
        parent = ticket_file.parent
        attachments_folder = parent.joinpath('attachments')
        r_attachments_folder = parent.joinpath('attachments_replies')

        attachments = ticket_obj['content']['attachments']

        if len(attachments) > 0:
            logger.debug('{} attachments to download'.format(len(attachments)))
            attachments_folder.mkdir(exist_ok=True)
            for attachment in attachments:
                url = attachment['url']['original'] + \
                    '?auth_token={0}'.format(token)
                fname = attachment['filename']
                attachment_file = attachments_folder.joinpath(fname)

                try:
                    if force or not attachment_file.exists():
                        r = requests.get(url, timeout=timeout)
                        with attachment_file.open('wb') as writer:
                            writer.write(r.content)
                        results.add_downloaded()

                    else:
                        logger.debug('Skipping {}'.format(str(attachment_file)))
                        results.add_skippped()

                except Exception as e:
                    logger.error('Error when processing attachment {}\r\n{}'.format(url,str(e)))

        replies_file = parent.joinpath('replies.json')
        if replies_file.exists():
            with replies_file.open('r') as reader:
                replies_obj = json.loads(reader.read())
                for reply in replies_obj:
                    if 'content' in reply:
                        r_attachments = reply['content']['attachments']
                        if len(r_attachments) > 0:
                            logger.debug('{} reply attachments to download'.format(len(r_attachments)))
                            r_attachments_folder.mkdir(exist_ok=True)
                            for attachment in r_attachments:
                                url = attachment['url']['original'] + \
                                    '?auth_token={0}'.format(token)
                                fname = attachment['filename']
                                attachment_file = r_attachments_folder.joinpath(fname)
                                try:
                                    if force or not attachment_file.exists():
                                        r = requests.get(url, timeout=timeout)
                                        with attachment_file.open('wb') as writer:
                                            writer.write(r.content)
                                        results.add_downloaded()
                                    else:
                                        logger.debug('Skipping {}'.format(str(attachment_file)))
                                        results.add_skippped()
                                except Exception as e:
                                    logger.error('Error when processing attachment {}\r\n{}'.format(url,str(e)))
    return results

def validate_date(ctx, param, value):
    try:
        if value:
            return pytz.utc.localize(dateutil.parser.parse(value))
        else:
            return None
    except Exception:
        raise click.BadParameter(
            'Please pass a valid ISO 8601 date like 2019-11-28')


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option('-l', '--loglevel', type=click.Choice(['error', 'warn', 'info', 'debug']), default='warn')
@click.option('-c', '--config', type=click.Path(exists=True), default=os.path.realpath('config.yaml'), help="Defaults to current folder \"config.yaml\"")
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
        EXPORT_FOLDER = Path(obj.get_config()['export_folder'])
        users_file = EXPORT_FOLDER.joinpath('users.json')
        with users_file.open('w') as writer:
            writer.write(json.dumps(users))
        click.echo('{} users exported to {}'.format(len(users),  click.format_filename(str(users_file))))

    except Exception as e:
        click.secho(str(e), fg='red')
        ctx.abort()


@cli.command(help="Exports the labels")
@click.pass_context
def labels(ctx):
    obj = ctx.obj['exporter']
    try:
        labels = obj.get_labels()
        EXPORT_FOLDER = Path(obj.get_config()['export_folder'])
        labels_file = EXPORT_FOLDER.joinpath('labels.json')
        with labels_file.open('w') as writer:
            writer.write(json.dumps(labels))
        click.echo('{} labels exported to {}'.format(len(labels), click.format_filename(str(labels_file))))
    except Exception as e:
        click.secho(str(e), fg='red')
        ctx.abort()


@cli.command(help="Exports the teams")
@click.pass_context
def teams(ctx):
    obj = ctx.obj['exporter']
    try:
        teams = obj.get_teams()
        EXPORT_FOLDER = Path(obj.get_config()['export_folder'])
        teams_file = EXPORT_FOLDER.joinpath('teams.json')
        with teams_file.open('w') as writer:
            writer.write(json.dumps(teams))
        click.echo('{} teams exported to {}'.format(len(teams), click.format_filename(str(teams_file))))
    except Exception as e:
        click.secho(str(e), fg='red')
        ctx.abort()


@cli.command(help="Exports the snippets")
@click.pass_context
def snippets(ctx):
    obj = ctx.obj['exporter']
    try:
        snippets = obj.get_snippets()
        EXPORT_FOLDER = Path(obj.get_config()['export_folder'])
        snippets_file = EXPORT_FOLDER.joinpath('snippets.json')
        with snippets_file.open('w') as writer:
            writer.write(json.dumps(snippets))
        click.echo('{} snippets exported to {}'.format(len(snippets), click.format_filename(str(snippets_file))))
    except Exception as e:
        click.secho(str(e), fg='red')
        ctx.abort()


@cli.command(help="Exports the forwarding addresses")
@click.pass_context
def emails(ctx):
    obj = ctx.obj['exporter']
    try:
        emails = obj.get_emails()
        EXPORT_FOLDER = Path(obj.get_config()['export_folder'])
        emails_file = EXPORT_FOLDER.joinpath('emails.json')
        with emails_file.open('w') as writer:
            writer.write(json.dumps(emails))
        click.echo('{} emails exported to {}'.format(len(emails),  click.format_filename(str(emails_file))))
    except Exception as e:
        click.secho(str(e), fg='red')
        ctx.abort()


@cli.command(help="Exports all tickets in a folder structure")
@click.option('-s', '--since-date', callback=validate_date, default='2000-01-01', help="Date since you want to export data in ISO format, example: 2017-11-28")
@click.pass_context
def export_tickets(ctx, since_date):
    obj = ctx.obj['exporter']

    EXPORT_FOLDER = Path(obj.get_config()['export_folder'])
    # Create the base folder if it does not exist
    EXPORT_FOLDER.mkdir(parents=True, exist_ok=True)
    
    tickets_iterator = obj.get_tickets(per_page=TICKETS_PAGE, since_date=since_date.isoformat())

    result = next(tickets_iterator)
    click.echo('{} pages of {} tickets each to download'.format(result.total_pages, TICKETS_PAGE))
    with click.progressbar(length= result.total_pages * TICKETS_PAGE,
                        label='Downloading tickets') as bar:
        while result:
            bar.update(result.page * TICKETS_PAGE)
            tickets = result.data
            # click.echo('{:3d}|{:3d}|{:3d}'.format(result.page, result.total_pages, len(tickets)))
            for ticket in tickets:
                save_ticket(EXPORT_FOLDER, ticket)
            
            result = next(tickets_iterator, False)

@cli.command(help="Exports all replies from the tickets stored")
@click.option('-s', '--since-date', callback=validate_date, default='2000-01-01', help="Date since you want to export data in ISO format, example: 2017-11-28")
@click.option('-f', '--force', is_flag=True, help="Don't skip downloaded files")
@click.pass_context
def export_replies(ctx, since_date, force):
    obj = ctx.obj['exporter']

    EXPORT_FOLDER = Path(obj.get_config()['export_folder'])
    PROCS = obj.get_config()['download_threads']

    # Get the current tickets
    tickets = list(EXPORT_FOLDER.joinpath('tickets').glob('**/ticket.json'))

    def save(ticket):
        return save_replies(obj, ticket, since_date, force)

    with Pool(PROCS) as p:
        click.echo('Starting the replies parallel download...')
        results = p.map(save, tickets)
    writes = results.count(RESULTS_DOWNLOAD)
    processed = results.count(RESULTS_SKIPPED) + writes
    total = results.count(RESULTS_OLD) + processed
    click.echo('Wrote {} out of {} checked replies from {} processed tickets'.format(writes, processed, total))


@cli.command(help="Exports all comments from the tickets stored")
@click.option('-s', '--since-date', callback=validate_date, default='2000-01-01', help="Date since you want to export data in ISO format, example: 2017-11-28")
@click.option('-f', '--force', is_flag=True, help="Don't skip downloaded files")
@click.pass_context
def export_comments(ctx, since_date, force):
    obj = ctx.obj['exporter']

    EXPORT_FOLDER = Path(obj.get_config()['export_folder'])
    PROCS = obj.get_config()['download_threads']

    # Get the current tickets
    tickets = list(EXPORT_FOLDER.joinpath('tickets').glob('**/ticket.json'))

    def save(ticket):
        return save_comments(obj, ticket, since_date, force)

    with Pool(PROCS) as p:
        click.echo('Starting the comments parallel download...')
        results = p.map(save, tickets)

    writes = results.count(RESULTS_DOWNLOAD)
    processed = results.count(RESULTS_SKIPPED) + writes
    total = results.count(RESULTS_OLD) + processed
    click.echo('Wrote {} out of {} checked comments from {} processed tickets'.format(writes, processed, total))

@cli.command(help="Exports all attachments from the tickets stored")
@click.option('-s', '--since-date', callback=validate_date, default='2000-01-01', help="Date since you want to export data in ISO format, example: 2017-11-28")
@click.option('-f', '--force', is_flag=True, help="Don't skip downloaded files")
@click.pass_context
def export_attachments(ctx, force, since_date):
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
        return save_attachments(TOKEN, TIMEOUT, ticket, since_date, force)

    with Pool(PROCS) as p:
        click.echo('Starting the download...')
        results = p.map(save, tickets)

    written = sum(map(lambda r: r.downloaded, results))
    skipped = sum(map(lambda r: r.skipped, results))
    click.echo('{} attachments written and {} skipped'.format(written, skipped))


@cli.command(help="Export all metadata")
@click.option('-f', '--force', is_flag=True, help="Don't skip downloaded files")
@click.pass_context
def all_metadata(ctx, force):
    click.secho('# Exporting account metadata',fg='green')
    ctx.invoke(labels)
    ctx.invoke(snippets)
    ctx.invoke(teams)
    ctx.invoke(users)

@cli.command(help="Export all ticket info: tickets, replies, comments and attachments")
@click.option('-s', '--since-date', callback=validate_date, default='2000-01-01', help="Date since you want to export data in ISO format, example: 2017-11-28")
@click.pass_context
def all_tickets(ctx, since_date):
    click.secho('# Exporting tickets',fg='green')
    ctx.invoke(export_tickets, since_date=since_date)
    click.secho('# Exporting replies',fg='green')
    ctx.invoke(export_replies, since_date=since_date, force=True)
    click.secho('# Exporting comments',fg='green')
    ctx.invoke(export_comments, since_date=since_date, force=True)
    click.secho('# Exporting attachments',fg='green')
    ctx.invoke(export_attachments, since_date=since_date, force=False)


@cli.command(help="Export all account info, both metadata and tickets")
@click.option('-s', '--since-date', callback=validate_date, default='2000-01-01', help="Date since you want to export data in ISO format, example: 2017-11-28")
@click.pass_context
def all(ctx, since_date):
    ctx.invoke(all_metadata)
    ctx.invoke(all_tickets, since_date=since_date)
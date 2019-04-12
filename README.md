# beedumper: backup your SupportBee data

A tool to backup all your data from [SupportBee](https://supportbee.com) ticketing tool

## Install

The package is published at PyPi as [beedumper](https://pypi.org/project/beedumper) so you can run `pip install beedumper` on your Python 3.6 environment to install the main command line interface. Alternatively you can also import  `beedumper.export.Exporter` class and work directly with the different methods outside the implemented [`cli`](https://github.com/CartoDB/beedumper/blob/master/beedumper/cli.py) logic.

**Note**: This tool requires python 3.6 or later to run.

## `beedumper` CLI command

```txt
$ beedumper -h
Usage: beedumper [OPTIONS] COMMAND [ARGS]...

  This command line tool helps you export your SupportBee account data.

Options:
  -l, --loglevel [error|warn|info|debug]
  -c, --config PATH               Defaults to current folder "config.yaml"
  -v, --version                   Show the version and exit.
  -h, --help                      Show this message and exit.

Commands:
  all                 Export all account info, both metadata and tickets
  all-metadata        Export all metadata
  all-tickets         Export all ticket info: tickets, replies, comments
                      and...
  emails              Exports the forwarding addresses
  export-attachments  Exports all attachments from the tickets stored
  export-comments     Exports all comments from the tickets stored
  export-replies      Exports all replies from the tickets stored
  export-tickets      Exports all tickets in a folder structure
  labels              Exports the labels
  snippets            Exports the snippets
  teams               Exports the teams
  users               Exports the users
```

Check the [example configuration](https://github.com/CartoDB/beedumper/blob/master/config.template.yaml) to set up your `config.yaml` file with SupportBee credentials and other settings.

Some subcommands may have further options, use `-h` to find out more about them.

## Tickets storage

The tickets are stored under a folder `tickets` below your defined output directory. For each ticket a folder is created with its `id` under an intermediate folder that is the modulus of the id by `99`. That is, under tickets you'll eventually have folders running from `00` to `98` spreading the tickets approximately evenly over them.

Under each ticket folder you'll eventually end with this structure:

* `ticket.json`: main information
* `replies.json`: array of replies made to the requester
* `comments.json`: comments made by agents
* `attachments`: folder with attachment files by the original requester
* `attachments_replies`: folder with attachments coming from the replies

## Recommended usage

It's recommended to first run the simple subcommands like `users` or `labels` to test things work as expected. Then you can start with `export-tickets --since-date` passing a recent date to download only a few tickets. Then you can do the same with `export-replies`, `export-comments`, and `export-attachments` sequentially, as replies and comments are based on existing tickets, and attachments use both tickets and replies JSON files.

If there are no issues on downloading those recent assets, you can then run `all` to download the full dump of tickets information and in subsequent executions use the `--since-date` parameter to only download tickets with `last_activity_at` metadata older than the passed timestamp to keep your dump updated with recent changes.
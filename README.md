# beedumper: backup your SupportBee data

A tool to back up all your data from the [SupportBee](https://supportbee.com) ticketing tool.

## Install

This project uses [uv](https://docs.astral.sh/uv/) to manage Python, dependencies and the virtual environment. From the repository folder run:

```sh
uv sync                      # creates .venv with Python 3.11 and installs dependencies
uv run beedumper -h          # runs the CLI inside the project environment
```

Any command can be run inside the environment with `uv run [command]`, for example `uv run beedumper -c config.yaml users`.

Alternatively you can import the `beedumper.export.Exporter` class and work directly with the different methods outside the implemented [`cli`](https://github.com/CartoDB/beedumper/blob/master/beedumper/cli.py) logic.

**Note**: This tool requires Python 3.11 or later to run.

## `beedumper` CLI command

```txt
$ uv run beedumper -h
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
  all-tickets         Export all ticket info: tickets, replies, comments...
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

Some subcommands have further options, use `-h` to find out more about them, for example `uv run beedumper export-replies -h`. Note that a valid config file must exist even to show a subcommand's help.

The ticket subcommands accept these options:

* `-s`, `--since-date`: only process tickets with activity after this date (ISO 8601, e.g. `2019-11-28`). Defaults to `2000-01-01`.
* `-f`, `--force` (`export-replies`, `export-comments`, `export-attachments`): download again files that already exist instead of skipping them.

`all-metadata` exports labels, snippets, teams and users. It does not include the forwarding addresses, run `emails` separately for those.

## Tickets storage

The tickets are stored under a folder `tickets` below your defined output directory. For each ticket a folder is created with its `id` under an intermediate folder that is the modulus of the id by `99`. That is, under tickets you'll eventually have folders running from `00` to `98` spreading the tickets approximately evenly over them.

Under each ticket folder you'll eventually end up with this structure:

* `ticket.json`: main information
* `replies.json`: array of replies made to the requester
* `comments.json`: comments made by agents
* `attachments`: folder with attachment files by the original requester
* `attachments_replies`: folder with attachments coming from the replies

## Recommended usage

It's recommended to first run the simple subcommands like `users` or `labels` to test things work as expected. Then you can start with `export-tickets --since-date` (e.g. `uv run beedumper export-tickets -s 2019-11-28`) passing a recent date to download only a few tickets. Then you can do the same with `export-replies`, `export-comments`, and `export-attachments` sequentially, as replies and comments are based on existing tickets, and attachments use both tickets and replies JSON files.

If there are no issues downloading those recent assets, you can then run `all` to download the full dump of tickets information. In subsequent executions use the `--since-date` parameter to only download tickets with `last_activity_at` metadata newer than the passed date, keeping your dump updated with recent changes. Note that `all` and `all-tickets` always download replies and comments again for those tickets, while existing attachments are skipped.

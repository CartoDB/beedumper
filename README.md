# beekeeper

A tool to export data from SupportBee ticketing tool


## Install

This is not uploaded to pip (yet) so you need to set up your environment like this:

* Clone this repo
* Install `poetry`: `pip install --user poetry`
* `poetry install`

That should leave your folder ready to start using `poetry run beekeeper` to execute the main command line interface but you can also import `beekeeper.export.Exporter` class and work directly with the different methods.

## `beekeeper` CLI command

```sh
poetry run beekeeper -h
Usage: beekeeper [OPTIONS] COMMAND [ARGS]...

  This command line tool helps you export your SupportBee account data.

Options:
  -l, --loglevel [error|warn|info|debug]
  -c, --config PATH               Defaults to current folder "config.yaml"
  -v, --version                   Show the version and exit.
  -h, --help                      Show this message and exit.

Commands:
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

Some subcommands may have further options, use `-h` to find out more about them.
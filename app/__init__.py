import os
import requests
import click


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    if ctx.invoked_subcommand is None:
        click.echo("Welcome to the odoc app 🥳")
        click.echo("Run odoc --help for options.")
import os
import click
import mock
import sys

from halo import Halo
from .pdoc import cli as pdoc

spinner = Halo(text='Loading', spinner='dots', text_color='cyan')


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    if ctx.invoked_subcommand is None:
        click.echo("Welcome to the odoc app 🥳")
        click.echo("Run odoc --help for options.")


def check_odoo_dir():
    """Checks if the current directory is an odoo root directory.

    If the current directory contains an `odoo` module and has an
    `odoo-bin` script, it's safe to assume that this is true.
    """
    spinner.start()

    dir_items = [i for i in os.listdir('.')]
    for i in dir_items:
        if 'odoo' and 'odoo-bin' in i:
            spinner.succeed("Yeap, we're in an odoo directory")
            return True


@cli.command()
@click.option('--html', default=True)
@click.argument('module')
def generate(module, html):
    """Generate docs"""
    if not check_odoo_dir():
        spinner.warn("This doesn't seem to be an odoo directory 🤔")

    MOCK_MODULES = ['babel', 'matplotlib', 'matplotlib.pyplot']
    for mod_name in MOCK_MODULES:
        sys.modules[mod_name] = mock.Mock()

    try:
        pdoc.main()
    except Exception as e:
        spinner.fail(f"Some shit went down: {e}")

import typer

from topicbuilder.app import display
from topicbuilder.tasks.discover import discover
from topicbuilder.tasks.factorize import factorize
from topicbuilder.tasks.label import label
from topicbuilder.tasks.screen import screen
from topicbuilder.tasks.structure import structure

app = typer.Typer(no_args_is_help=True, help="Topic modeling CLI with three independent tasks.")
app.command()(screen)
app.command()(discover)
app.command()(factorize)
app.command()(structure)
app.command()(label)
app.command()(display)

if __name__ == "__main__":
    app()

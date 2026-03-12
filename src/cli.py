import pathlib
from typing import Optional

import typer

from .orchestrator import run_analyze

app = typer.Typer(help="Brownfield Cartographer CLI")


@app.command()
def analyze(
    target: str = typer.Argument(
        ...,
        help="Path to a local repo or a GitHub URL to clone and analyze.",
    ),
    branch: Optional[str] = typer.Option(
        None, "--branch", "-b", help="Branch to use when cloning a GitHub URL."
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", "-o", help="Output directory for .cartography artifacts (default: <repo>/.cartography)."
    ),
) -> None:
    """
    Run the Cartographer analysis pipeline on the given target.
    """
    target_path = pathlib.Path(target).expanduser()
    out = pathlib.Path(output_dir).expanduser() if output_dir else None
    run_analyze(target_path, branch=branch, output_dir=out)


if __name__ == "__main__":
    app()


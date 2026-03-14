import pathlib
from typing import Optional

import typer

from .orchestrator import run_analyze, run_query

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
    incremental: bool = typer.Option(
        False, "--incremental", "-i", help="Re-analyze only changed files since last run (merge into existing .cartography)."
    ),
) -> None:
    """
    Run the full Cartographer pipeline: Surveyor -> Hydrologist -> Semanticist -> Archivist.
    Produces CODEBASE.md, onboarding_brief.md, module_graph.json, lineage_graph.json, trace, semantic_index.
    """
    target_path = pathlib.Path(target).expanduser()
    out = pathlib.Path(output_dir).expanduser() if output_dir else None
    run_analyze(target_path, branch=branch, output_dir=out, incremental=incremental)


@app.command()
def query(
    target: str = typer.Argument(
        ...,
        help="Path to a local repo that has already been analyzed (has .cartography/).",
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", "-o", help="Path to .cartography directory (default: <target>/.cartography)."
    ),
) -> None:
    """
    Interactive query mode: load .cartography and run Navigator (find_implementation, trace_lineage, blast_radius, explain_module).
    """
    repo_path = pathlib.Path(target).expanduser()
    if not repo_path.is_dir():
        typer.echo("Target must be an existing directory.", err=True)
        raise typer.Exit(1)
    out = pathlib.Path(output_dir).expanduser() if output_dir else None
    run_query(repo_path, cartography_dir=out)


if __name__ == "__main__":
    app()


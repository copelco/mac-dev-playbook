#!/usr/bin/env python3
"""Time Machine Exclusion Management Tool"""

import subprocess
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()
COMMON_PATTERNS = [".direnv", ".venv", "node_modules"]
COMMON_CACHE_DIRS = ["~/.cache", "~/.gradle/caches"]


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=check)
    except subprocess.CalledProcessError as e:
        if check:
            console.print(f"[red]Command failed: {' '.join(cmd)} - {e}[/red]")
        raise


def is_excluded(path: Path) -> bool:
    """Check if path is excluded from Time Machine."""
    result = run_command(["tmutil", "isexcluded", str(path)], check=False)
    return "[Excluded]" in result.stdout


def toggle_exclusion(path: Path, exclude: bool = True) -> bool:
    """Add or remove Time Machine exclusion for path."""
    if not path.exists():
        console.print(f"[yellow]Path does not exist: {path}[/yellow]")
        return False

    action = "addexclusion" if exclude else "removeexclusion"
    current_status = is_excluded(path)

    if exclude and current_status:
        console.print(f"[blue]Already excluded: {path}[/blue]")
        return True
    elif not exclude and not current_status:
        console.print(f"[blue]Not excluded: {path}[/blue]")
        return True

    try:
        run_command(["tmutil", action, str(path)])
        status = "Added" if exclude else "Removed"
        console.print(f"[green]{status} exclusion: {path}[/green]")
        return True
    except subprocess.CalledProcessError:
        return False


def find_pattern_dirs(root: Path, patterns: list[str]) -> list[Path]:
    """Find directories matching patterns under root."""
    if not root.exists():
        console.print(f"[red]Root path does not exist: {root}[/red]")
        return []

    found = []
    for pattern in patterns:
        try:
            result = run_command(
                ["find", str(root), "-type", "d", "-name", pattern, "-prune"]
            )
            for line in result.stdout.strip().split("\n"):
                if line:
                    path = Path(line)
                    if path.exists():
                        found.append(path)
        except subprocess.CalledProcessError:
            continue

    return sorted(set(found))


def get_dir_size(path: Path) -> str:
    """Get human-readable directory size."""
    try:
        result = run_command(["du", "-sh", str(path)])
        return result.stdout.split("\t")[0]
    except subprocess.CalledProcessError:
        return "Unknown"


def create_status_table(dirs: list[Path], show_size: bool = False) -> Table:
    """Create a Rich table showing directory status."""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Path", style="cyan")
    table.add_column("Status", style="green")
    if show_size:
        table.add_column("Size", style="blue")

    for path in dirs:
        excluded = is_excluded(path)
        status = "✓ Excluded" if excluded else "✗ Not excluded"
        row = [str(path), status]
        if show_size:
            row.append(get_dir_size(path))
        table.add_row(*row)

    return table


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Time Machine Exclusion Management Tool"""
    pass


@cli.command()
@click.option("--root", "-r", default="~/projects", help="Root directory to search")
@click.option("--pattern", "-p", multiple=True, help="Patterns to search for")
@click.option("--dry-run", "-n", is_flag=True, help="Show what would be done")
def exclude(root, pattern, dry_run):
    """Exclude directories matching patterns."""
    root_path = Path(root).expanduser().resolve()
    patterns = list(pattern) if pattern else COMMON_PATTERNS
    dirs = find_pattern_dirs(root_path, patterns)

    if not dirs:
        console.print("[yellow]No directories found[/yellow]")
        return

    console.print(f"\n[bold]Found {len(dirs)} directories:[/bold]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Path", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Action", style="yellow")

    for path in dirs:
        excluded = is_excluded(path)
        status = "Excluded" if excluded else "Not excluded"
        if excluded:
            action = "Skip"
        else:
            action = "Would exclude" if dry_run else "Exclude"
        table.add_row(str(path), status, action)

    console.print(table)

    if dry_run:
        console.print("\n[yellow]Dry run - no changes made[/yellow]")
        return

    count = sum(toggle_exclusion(p, True) for p in dirs if not is_excluded(p))
    console.print(f"\n[bold green]Excluded {count} directories[/bold green]")


@cli.command()
@click.option("--root", "-r", default="~/projects", help="Root directory to search")
@click.option("--pattern", "-p", multiple=True, help="Patterns to search for")
@click.option("--dry-run", "-n", is_flag=True, help="Show what would be done")
def include(root, pattern, dry_run):
    """Include (remove exclusion) directories matching patterns."""
    root_path = Path(root).expanduser().resolve()
    patterns = list(pattern) if pattern else COMMON_PATTERNS
    dirs = find_pattern_dirs(root_path, patterns)
    excluded_dirs = [d for d in dirs if is_excluded(d)]

    if not excluded_dirs:
        console.print("[yellow]No excluded directories found[/yellow]")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Path", style="cyan")
    table.add_column("Action", style="yellow")

    for path in excluded_dirs:
        action = "Would include" if dry_run else "Include"
        table.add_row(str(path), action)

    console.print(table)

    if dry_run:
        console.print("\n[yellow]Dry run - no changes made[/yellow]")
        return

    count = sum(toggle_exclusion(p, False) for p in excluded_dirs)
    console.print(f"\n[bold green]Included {count} directories[/bold green]")


@cli.command()
@click.option("--root", "-r", default="~/projects", help="Root directory to check")
@click.option("--pattern", "-p", multiple=True, help="Patterns to search for")
def status(root, pattern):
    """Show exclusion status of directories."""
    root_path = Path(root).expanduser().resolve()
    patterns = list(pattern) if pattern else COMMON_PATTERNS
    dirs = find_pattern_dirs(root_path, patterns)

    if not dirs:
        console.print("[yellow]No directories found[/yellow]")
        return

    table = create_status_table(dirs, show_size=True)
    console.print(table)

    excluded_count = sum(1 for d in dirs if is_excluded(d))
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"Total: {len(dirs)}")
    console.print(f"Excluded: {excluded_count}")
    console.print(f"Not excluded: {len(dirs) - excluded_count}")


@cli.command()
@click.option("--dry-run", "-n", is_flag=True, help="Show what would be done")
def cache(dry_run):
    """Exclude common cache directories."""
    existing_dirs = []
    for cache_dir in COMMON_CACHE_DIRS:
        path = Path(cache_dir).expanduser().resolve()
        if path.exists():
            existing_dirs.append(path)

    if not existing_dirs:
        console.print("[yellow]No cache directories found[/yellow]")
        return

    console.print(f"\n[bold]Found {len(existing_dirs)} cache directories:[/bold]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Path", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Action", style="yellow")
    table.add_column("Size", style="blue")

    for path in existing_dirs:
        excluded = is_excluded(path)
        status = "Excluded" if excluded else "Not excluded"
        if excluded:
            action = "Skip"
        else:
            action = "Would exclude" if dry_run else "Exclude"
        size = get_dir_size(path)
        table.add_row(str(path), status, action, size)

    console.print(table)

    if dry_run:
        console.print("\n[yellow]Dry run - no changes made[/yellow]")
        return

    count = sum(toggle_exclusion(p, True) for p in existing_dirs if not is_excluded(p))
    console.print(f"\n[bold green]Excluded {count} cache directories[/bold green]")


@cli.command()
@click.argument("paths", nargs=-1, required=True)
@click.option("--dry-run", "-n", is_flag=True, help="Show what would be done")
def add(paths, dry_run):
    """Add specific paths to exclusions."""
    resolved_paths = [Path(p).expanduser().resolve() for p in paths]

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Path", style="cyan")
    table.add_column("Action", style="yellow")

    for path in resolved_paths:
        action = "Would exclude" if dry_run else "Exclude"
        table.add_row(str(path), action)

    console.print(table)

    if dry_run:
        console.print("\n[yellow]Dry run - no changes made[/yellow]")
        return

    count = sum(toggle_exclusion(p, True) for p in resolved_paths)
    console.print(f"\n[bold green]Excluded {count}/{len(paths)} paths[/bold green]")


@cli.command()
@click.argument("paths", nargs=-1, required=True)
@click.option("--dry-run", "-n", is_flag=True, help="Show what would be done")
def remove(paths, dry_run):
    """Remove specific paths from exclusions."""
    resolved_paths = [Path(p).expanduser().resolve() for p in paths]

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Path", style="cyan")
    table.add_column("Action", style="yellow")

    for path in resolved_paths:
        action = "Would include" if dry_run else "Include"
        table.add_row(str(path), action)

    console.print(table)

    if dry_run:
        console.print("\n[yellow]Dry run - no changes made[/yellow]")
        return

    count = sum(toggle_exclusion(p, False) for p in resolved_paths)
    console.print(f"\n[bold green]Included {count}/{len(paths)} paths[/bold green]")


if __name__ == "__main__":
    cli()

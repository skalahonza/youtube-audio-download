#!/usr/bin/env python3
"""YouTube Channel Audio Downloader — downloads channel videos as MP3."""

import sys
from pathlib import Path

import questionary
import typer
import yt_dlp
from rich.console import Console
from rich.table import Table

console = Console()
app = typer.Typer(add_completion=False, help="Download YouTube channel videos as MP3.")


def resolve_channel_url(channel: str) -> str:
    if channel.startswith("http://") or channel.startswith("https://"):
        return channel
    handle = channel if channel.startswith("@") else f"@{channel}"
    return f"https://www.youtube.com/{handle}/videos"


def format_duration(seconds) -> str:
    if not seconds:
        return "--:--"
    seconds = int(seconds)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fetch_videos(channel_url: str, limit: int | None) -> list[dict]:
    console.print(f"[cyan]Fetching video list from:[/cyan] {channel_url}\n")

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "ignoreerrors": True,
        "playlistend": limit,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    if not info:
        console.print("[red]Could not fetch channel info. Check the channel name and try again.[/red]")
        raise typer.Exit(1)

    entries = [e for e in (info.get("entries") or []) if e]
    if not entries:
        console.print("[red]No videos found for this channel.[/red]")
        raise typer.Exit(1)

    return [
        {
            "id": e.get("id", ""),
            "title": e.get("title") or "Untitled",
            "duration": e.get("duration"),
            "upload_date": e.get("upload_date", ""),
        }
        for e in entries
    ]


def display_videos(videos: list[dict]) -> None:
    table = Table(title=f"Found {len(videos)} video(s)", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=5, justify="right")
    table.add_column("Title")
    table.add_column("Duration", style="cyan", width=10, justify="right")
    table.add_column("Uploaded", style="green", width=12)

    for i, v in enumerate(videos, 1):
        date = v["upload_date"]
        if len(date) == 8:
            date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        table.add_row(str(i), v["title"], format_duration(v["duration"]), date or "unknown")

    console.print(table)


def filter_videos(videos: list[dict]) -> list[dict]:
    while True:
        term = questionary.text(
            "Filter by title (leave blank to show all):",
            default="",
        ).ask()

        if term is None:
            return videos

        needle = term.strip().lower()
        if not needle:
            return videos

        matched = [v for v in videos if needle in v["title"].lower()]
        if matched:
            console.print(f"[dim]{len(matched)} of {len(videos)} videos match '[bold]{term}[/bold]'[/dim]")
            return matched

        console.print(f"[yellow]No videos match '{term}'. Try a different filter.[/yellow]")


def select_videos(videos: list[dict]) -> list[dict]:
    visible = filter_videos(videos)

    console.print()
    mode = questionary.select(
        "How do you want to select videos?",
        choices=["Choose individually", f"Select all ({len(visible)})"],
    ).ask()

    if mode is None:
        return []
    if mode.startswith("Select all"):
        return visible

    selected = questionary.checkbox(
        "Select videos to download  (↑↓ navigate · Space select · Enter confirm):",
        choices=[
            questionary.Choice(
                title=f"{v['title'][:72]}  [{format_duration(v['duration'])}]",
                value=v,
            )
            for v in visible
        ],
    ).ask()

    return selected or []


def download_as_mp3(videos: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "ignoreerrors": True,
    }

    console.print(f"\n[green]Saving MP3s to:[/green] {output_dir.resolve()}\n")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for i, v in enumerate(videos, 1):
            console.rule(f"[bold cyan]{i}/{len(videos)}[/bold cyan] {v['title']}")
            url = f"https://www.youtube.com/watch?v={v['id']}"
            ydl.download([url])

    console.print(f"\n[bold green]Done![/bold green] {len(videos)} file(s) saved to {output_dir.resolve()}")


@app.command()
def main(
    channel: str = typer.Argument(help="Channel handle (e.g. @mkbhd), name, or full URL"),
    output: Path = typer.Option(Path("downloads"), "--output", "-o", help="Destination folder for MP3 files"),
    limit: int = typer.Option(None, "--limit", "-l", help="Max number of videos to fetch from the channel"),
) -> None:
    console.print("[bold cyan]YouTube Channel Audio Downloader[/bold cyan]\n")

    channel_url = resolve_channel_url(channel)
    videos = fetch_videos(channel_url, limit)
    display_videos(videos)

    selected = select_videos(videos)
    if not selected:
        console.print("[yellow]Nothing selected — exiting.[/yellow]")
        raise typer.Exit()

    console.print(f"\n[bold]Selected {len(selected)} video(s):[/bold]")
    for v in selected:
        console.print(f"  • {v['title']}")

    confirmed = questionary.confirm(f"\nDownload {len(selected)} video(s) as MP3?").ask()
    if not confirmed:
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit()

    download_as_mp3(selected, output)


if __name__ == "__main__":
    app()

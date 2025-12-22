"""Command-line interface for the News Curation Agent."""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.agent import NewsAgent, process_url, process_urls
from src.models.schemas import ProcessingStatus

# Configure logging with Rich handler for better formatting
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
)
logger = logging.getLogger(__name__)

app = typer.Typer(
    name="news-agent",
    help="Autonomous News Curation Agent - Extract, fact-check, and summarize content",
)
console = Console()


@app.command()
def process(
    url: str = typer.Argument(..., help="URL to process"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path (JSON)"
    ),
    skip_fact_check: bool = typer.Option(
        False, "--skip-fact-check", "-s", help="Skip fact-checking step"
    ),
    include_raw: bool = typer.Option(
        False, "--include-raw", "-r", help="Include raw extracted text"
    ),
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output as JSON only"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging (DEBUG level)"
    ),
):
    """Process a single URL and display the summary."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    if json_output:
        # Quiet mode for JSON output
        result = asyncio.run(
            process_url(
                url,
                skip_fact_check=skip_fact_check,
                include_raw_text=include_raw,
            )
        )
        output_json = result.model_dump_json(indent=2)

        if output:
            output.write_text(output_json)
        else:
            print(output_json)

        if result.status == ProcessingStatus.FAILED:
            raise typer.Exit(1)
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing URL...", total=None)

        result = asyncio.run(
            process_url(
                url,
                skip_fact_check=skip_fact_check,
                include_raw_text=include_raw,
            )
        )

        progress.update(task, completed=True)

    # Display results
    if result.status == ProcessingStatus.FAILED:
        console.print(f"[red]Error:[/red] {result.error}")
        raise typer.Exit(1)

    _display_result(result)

    if output:
        output.write_text(result.model_dump_json(indent=2))
        console.print(f"\n[green]Results saved to:[/green] {output}")


@app.command()
def batch(
    input_file: Path = typer.Argument(..., help="File containing URLs (one per line)"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path (JSON)"
    ),
    skip_fact_check: bool = typer.Option(
        False, "--skip-fact-check", "-s", help="Skip fact-checking step"
    ),
    include_raw: bool = typer.Option(
        False, "--include-raw", "-r", help="Include raw extracted text"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging (DEBUG level)"
    ),
):
    """Process multiple URLs from a file."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    if not input_file.exists():
        console.print(f"[red]Error:[/red] File not found: {input_file}")
        raise typer.Exit(1)

    urls = [line.strip() for line in input_file.read_text().splitlines() if line.strip()]

    if not urls:
        console.print("[red]Error:[/red] No URLs found in file")
        raise typer.Exit(1)

    console.print(f"Processing {len(urls)} URLs...")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Processing {len(urls)} URLs...", total=None)

        results = asyncio.run(
            process_urls(
                urls,
                skip_fact_check=skip_fact_check,
                include_raw_text=include_raw,
            )
        )

        progress.update(task, completed=True)

    # Summary
    completed = sum(1 for r in results if r.status == ProcessingStatus.COMPLETED)
    failed = sum(1 for r in results if r.status == ProcessingStatus.FAILED)

    console.print(f"\n[green]Completed:[/green] {completed}")
    console.print(f"[red]Failed:[/red] {failed}")

    # Display results table
    table = Table(title="Processing Results")
    table.add_column("URL", style="cyan", no_wrap=True, max_width=50)
    table.add_column("Status", style="green")
    table.add_column("Title", max_width=40)
    table.add_column("Sentiment")

    for result in results:
        status_style = "green" if result.status == ProcessingStatus.COMPLETED else "red"
        title = result.content.title[:40] if result.content and result.content.title else "N/A"
        sentiment = result.summary.sentiment.value if result.summary and result.summary.sentiment else "N/A"

        table.add_row(
            result.url[:50],
            f"[{status_style}]{result.status.value}[/{status_style}]",
            title,
            sentiment,
        )

    console.print(table)

    # Show detailed error information for failed URLs
    failed_results = [r for r in results if r.status == ProcessingStatus.FAILED]
    if failed_results:
        console.print("\n[bold red]Failed URL Details:[/bold red]")
        for result in failed_results:
            console.print(f"\n  [cyan]{result.url}[/cyan]")
            error_msg = result.error or "Unknown error"
            # Provide helpful hints for common errors
            if "403" in error_msg:
                console.print(f"    [red]Error:[/red] {error_msg}")
                console.print("    [dim]Hint: Site has bot protection or paywall. Try --verbose for details.[/dim]")
            elif "timeout" in error_msg.lower():
                console.print(f"    [red]Error:[/red] {error_msg}")
                console.print("    [dim]Hint: Site took too long to respond (Cloudflare challenge?).[/dim]")
            else:
                console.print(f"    [red]Error:[/red] {error_msg}")

    if output:
        output_data = [r.model_dump() for r in results]
        output.write_text(json.dumps(output_data, indent=2, default=str))
        console.print(f"\n[green]Results saved to:[/green] {output}")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
):
    """Start the API server."""
    import uvicorn

    console.print(f"Starting API server at http://{host}:{port}")
    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def check_config():
    """Check configuration and API keys."""
    from src.config import get_settings

    settings = get_settings()

    table = Table(title="Configuration Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Value")

    # Check Gemini API key
    gemini_status = "✅" if settings.gemini_api_key else "❌"
    gemini_value = "Configured" if settings.gemini_api_key else "Missing"
    table.add_row("Gemini API Key", gemini_status, gemini_value)

    # Check Fact Check API key
    fc_status = "✅" if settings.google_fact_check_api_key else "⚠️"
    fc_value = "Configured" if settings.google_fact_check_api_key else "Optional"
    table.add_row("Google Fact Check API", fc_status, fc_value)

    # Check storage
    storage_status = "✅" if settings.has_storage else "⚠️"
    storage_value = (
        "Firebase" if settings.has_firebase
        else "Supabase" if settings.has_supabase
        else "Not configured"
    )
    table.add_row("Storage Backend", storage_status, storage_value)

    # Model
    table.add_row("Gemini Model", "ℹ️", settings.gemini_model)

    console.print(table)

    if not settings.gemini_api_key:
        console.print("\n[red]Error:[/red] Gemini API key is required")
        console.print("Set GEMINI_API_KEY in your .env file")
        raise typer.Exit(1)


def _display_result(result):
    """Display a processed result in a nice format."""
    # Title panel
    title = result.content.title if result.content else "Unknown Title"
    console.print(Panel(title, title="[bold blue]Content[/bold blue]"))

    # Metadata
    if result.content:
        meta_table = Table(show_header=False, box=None)
        meta_table.add_column("Key", style="dim")
        meta_table.add_column("Value")

        if result.content.author:
            meta_table.add_row("Author", result.content.author)
        if result.content.published_date:
            meta_table.add_row("Published", str(result.content.published_date))
        meta_table.add_row("Source", result.source_type.value)
        meta_table.add_row("Word Count", str(result.content.word_count))
        if result.processing_time_ms:
            meta_table.add_row("Processing Time", f"{result.processing_time_ms}ms")

        console.print(meta_table)

    # Executive Summary
    if result.summary:
        console.print("\n[bold]Executive Summary[/bold]")
        console.print(result.summary.executive_summary)

        # Key Points
        console.print("\n[bold]Key Points[/bold]")
        for i, point in enumerate(result.summary.key_points, 1):
            console.print(f"  {i}. {point}")

        # Sentiment
        sentiment_colors = {
            "positive": "green",
            "negative": "red",
            "neutral": "yellow",
            "mixed": "blue",
        }
        sentiment = result.summary.sentiment.value
        color = sentiment_colors.get(sentiment, "white")
        console.print(f"\n[bold]Sentiment:[/bold] [{color}]{sentiment}[/{color}]")

        # Entities
        if result.summary.entities:
            console.print("\n[bold]Key Entities[/bold]")
            for entity in result.summary.entities[:5]:
                console.print(f"  • {entity.text} ({entity.type.value})")

        # Topics
        if result.summary.topics:
            topics_str = ", ".join(result.summary.topics)
            console.print(f"\n[bold]Topics:[/bold] {topics_str}")

    # Fact Check Results
    if result.fact_check and result.fact_check.claims_analyzed > 0:
        console.print("\n[bold]Fact-Check Results[/bold]")
        console.print(f"  Claims analyzed: {result.fact_check.claims_analyzed}")

        if result.fact_check.verified_claims:
            console.print("  [green]Verified Claims:[/green]")
            for claim in result.fact_check.verified_claims[:3]:
                rating_colors = {
                    "true": "green",
                    "mostly_true": "green",
                    "mixed": "yellow",
                    "mostly_false": "red",
                    "false": "red",
                }
                color = rating_colors.get(claim.rating.value, "white")
                console.print(f"    • [{color}]{claim.rating.value}[/{color}]: {claim.claim[:80]}...")
                console.print(f"      Source: {claim.source}")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()



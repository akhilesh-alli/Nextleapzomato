"""
ui/cli.py
---------
Interactive Command-Line Interface for AI Restaurant Recommendations.
Built with `rich` for modern terminal typography, styled panels, and progress spinners.

Features:
  - Interactive preference collection with input validation
  - CLI argument support (--location, --cuisine, --budget, etc.)
  - Progress spinner while filtering and querying the LLM
  - Styled restaurant recommendation cards with ratings and cost badges
  - Comparative AI summary block
  - EC-701: Required location validation
  - EC-703: Graceful exit on Ctrl+C (KeyboardInterrupt)
"""

import argparse
import sys
import os
import time
from typing import Optional

# Force UTF-8 encoding on Windows console (prevents cp1252 emoji crash)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Setup path so importing from src and config works from any directory
import pathlib
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.filtering.models import UserPreferences
from src.orchestrator import Orchestrator, RecommendationResult

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.prompt import Prompt, Confirm, FloatPrompt
    from rich.status import Status
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None


def print_banner() -> None:
    """Display stylized welcome banner."""
    if RICH_AVAILABLE:
        banner_text = Text()
        banner_text.append("🍽️  NEXT LEAP AI — RESTAURANT CONCIERGE\n", style="bold cyan")
        banner_text.append(
            "Personalized dining recommendations powered by real Zomato data & LLMs",
            style="italic dim",
        )
        console.print(Panel(banner_text, border_style="cyan", padding=(1, 2)))
    else:
        print("=" * 60)
        print("🍽️  NEXT LEAP AI — RESTAURANT CONCIERGE")
        print("Personalized dining recommendations")
        print("=" * 60)


def collect_interactive_preferences() -> UserPreferences:
    """
    Prompt the user interactively for dining preferences with validation.
    Handles EC-701 (location required) and EC-703 (graceful Ctrl+C exit).
    """
    if RICH_AVAILABLE:
        console.print("\n[bold yellow]Tell us about your dining plans:[/bold yellow]\n")

        # 1. Location (EC-701: Must not be empty)
        location = ""
        while not location:
            location = Prompt.ask("[bold green]📍 City or Neighborhood[/bold green] (e.g. Bangalore, Indiranagar, Koramangala)").strip()
            if not location:
                console.print("[red]Location is required to find restaurants. Please enter a city or area.[/red]")

        # 2. Budget Tier
        console.print("\n[bold]Select Budget Tier:[/bold]")
        console.print("  [1] Low     (Under ₹300 for two)")
        console.print("  [2] Medium  (₹300 - ₹800 for two)")
        console.print("  [3] High    (Above ₹800 for two)")
        console.print("  [4] Any     (No budget restriction)")
        budget_choice = Prompt.ask("[bold green]💳 Budget[/bold green]", choices=["1", "2", "3", "4"], default="4")
        budget_map = {"1": "low", "2": "medium", "3": "high", "4": ""}
        budget = budget_map.get(budget_choice, "")

        # 3. Cuisine
        cuisine = Prompt.ask("\n[bold green]🍜 Preferred Cuisine[/bold green] (e.g. Italian, Biryani, North Indian, or leave blank for any)").strip()

        # 4. Minimum Rating
        min_rating = 0.0
        try:
            rating_input = Prompt.ask("[bold green]⭐ Minimum Rating[/bold green] (0.0 to 5.0, default 3.5)", default="3.5")
            min_rating = float(rating_input)
            min_rating = max(0.0, min(5.0, min_rating))
        except ValueError:
            min_rating = 3.5

        # 5. Delivery & Booking
        online_delivery = Confirm.ask("\n[bold green]🛵 Require Online Delivery?[/bold green]", default=False)
        table_booking = Confirm.ask("[bold green]📅 Require Table Booking?[/bold green]", default=False)

        # 6. Additional Notes
        extra_notes = Prompt.ask("\n[bold green]📝 Any special notes / occasion?[/bold green] (e.g. quiet romantic date, rooftop, fast service)").strip()

    else:
        # Fallback for plain terminal without rich
        location = ""
        while not location:
            location = input("Location (required, e.g. Bangalore): ").strip()
        budget = input("Budget (low/medium/high/any): ").strip().lower()
        if budget == "any":
            budget = ""
        cuisine = input("Cuisine (optional): ").strip()
        min_rating_raw = input("Min Rating (default 3.5): ").strip()
        min_rating = float(min_rating_raw) if min_rating_raw else 3.5
        online_delivery = input("Delivery required? (y/n): ").strip().lower().startswith("y")
        table_booking = input("Booking required? (y/n): ").strip().lower().startswith("y")
        extra_notes = input("Additional notes: ").strip()

    return UserPreferences(
        location=location,
        budget=budget,
        cuisine=cuisine,
        min_rating=min_rating,
        online_delivery=online_delivery,
        table_booking=table_booking,
        extra_notes=extra_notes,
    )


def display_results(result: RecommendationResult) -> None:
    """Render formatted recommendations and summary to terminal."""
    if not RICH_AVAILABLE:
        # Plain terminal formatting
        if result.error:
            print(f"\nError: {result.error}\n")
            return
        print("\n" + "=" * 50)
        print("TOP RECOMMENDATIONS")
        print("=" * 50)
        for r in result.recommendations:
            print(f"\n#{r.rank} {r.name}")
            print(f"  Cuisine : {r.cuisine}")
            print(f"  Rating  : {r.rating} / 5.0")
            print(f"  Cost    : Rs. {r.cost} for two")
            print(f"  Location: {r.location}")
            print(f"  Why     : {r.explanation}")
        if result.summary:
            print("\nSUMMARY:\n" + result.summary)
        return

    # Rich formatted output
    if result.error:
        console.print(Panel(
            f"[bold red]⚠️  {result.error}[/bold red]",
            title="Search Notice",
            border_style="red",
        ))
        return

    # Relaxation notice
    if result.filter_result and result.filter_result.relaxed:
        console.print(
            f"\n[bold yellow]ℹ️  Filter Relaxation Note:[/bold yellow] "
            f"{result.filter_result.relaxation_note}"
        )

    if result.is_fallback:
        console.print(
            "[bold orange1]⚠️  AI Service Fallback: Displaying top-rated restaurants verified from database.[/bold orange1]"
        )

    console.print(f"\n[bold cyan]Found {len(result.recommendations)} Curated Recommendations:[/bold cyan]\n")

    for r in result.recommendations:
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold dim", width=16)
        table.add_column()

        table.add_row("Cuisine", f"[white]{r.cuisine or 'Various'}[/white]")
        table.add_row("Rating", f"[bold yellow]⭐ {r.rating:.1f}[/bold yellow] / 5.0")
        table.add_row("Estimated Cost", f"[green]₹{r.cost}[/green] for two")
        table.add_row("Location", f"[cyan]📍 {r.location}[/cyan]")

        if r.explanation:
            table.add_row("Why Recommend", f"[italic white]{r.explanation}[/italic white]")

        card_title = f"[bold green]#{r.rank}  {r.name}[/bold green]"
        if r.is_hallucinated:
            card_title += " [dim](Unverified Name)[/dim]"

        console.print(Panel(
            table,
            title=card_title,
            title_align="left",
            border_style="green",
            padding=(1, 2),
        ))

    # Summary Panel
    if result.summary:
        console.print(Panel(
            f"[italic white]{result.summary}[/italic white]",
            title="[bold blue]✨ Concierge Summary[/bold blue]",
            title_align="left",
            border_style="blue",
            padding=(1, 2),
        ))

    # Telemetry Footer
    timings = result.timings
    total_ms = timings.get("total_time_ms", 0.0)
    filter_ms = timings.get("filter_time_ms", 0.0)
    llm_ms = timings.get("llm_time_ms", 0.0)

    console.print(
        f"[dim]⚡ Completed in {total_ms/1000:.2f}s "
        f"(Filter: {filter_ms:.0f}ms | LLM: {llm_ms:.0f}ms) | "
        f"Candidates evaluated: {result.candidate_count}[/dim]\n"
    )


def main() -> None:
    """CLI Entry Point."""
    parser = argparse.ArgumentParser(
        description="Next Leap AI — Restaurant Recommendation Concierge",
    )
    parser.add_argument("--location", type=str, help="City or area (e.g. Bangalore, Indiranagar)")
    parser.add_argument("--budget", type=str, choices=["low", "medium", "high", "any"], help="Budget tier")
    parser.add_argument("--cuisine", type=str, help="Cuisine preference (e.g. Italian, Biryani)")
    parser.add_argument("--min-rating", type=float, default=0.0, help="Minimum rating (0.0 to 5.0)")
    parser.add_argument("--delivery", action="store_true", help="Require online delivery")
    parser.add_argument("--booking", action="store_true", help="Require table booking")
    parser.add_argument("--notes", type=str, default="", help="Special preferences / notes")

    args = parser.parse_args()

    print_banner()

    try:
        # Check if run with CLI arguments or interactive mode
        if args.location:
            budget = "" if args.budget == "any" else (args.budget or "")
            prefs = UserPreferences(
                location=args.location,
                budget=budget,
                cuisine=args.cuisine or "",
                min_rating=args.min_rating,
                online_delivery=args.delivery,
                table_booking=args.booking,
                extra_notes=args.notes,
            )
        else:
            prefs = collect_interactive_preferences()

        # Execute recommendation pipeline with spinner
        if RICH_AVAILABLE:
            with Status("[bold cyan]Consulting restaurant database and AI concierge...[/bold cyan]", spinner="dots"):
                orchestrator = Orchestrator()
                result = orchestrator.recommend(prefs)
        else:
            print("\nSearching restaurants and consulting AI...")
            orchestrator = Orchestrator()
            result = orchestrator.recommend(prefs)

        display_results(result)

    except KeyboardInterrupt:
        # EC-703: Clean exit on Ctrl+C
        if RICH_AVAILABLE:
            console.print("\n\n[bold yellow]👋 Exiting. Have a delicious day![/bold yellow]\n")
        else:
            print("\nExiting. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()

"""CLI entry point for infra-cost-sentinel."""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import json

import typer
from rich.console import Console

from .aws_fetcher import AWSFetcher
from .analyzer import CostAnalyzer
from .dashboard import CostDashboard
from .demo import DemoDataGenerator


app = typer.Typer(
    name="infra-cost-sentinel",
    help="AWS Infrastructure Cost Analyzer - Monitor, analyze, and optimize cloud spending",
    no_args_is_help=True,
)
console = Console()


@app.command()
def analyze(
    profile: str | None = typer.Option(None, "--profile", "-p", help="AWS profile name"),
    region: str = typer.Option("us-east-1", "--region", "-r", help="Primary AWS region"),
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
    demo: bool = typer.Option(False, "--demo", help="Use demo data instead of real AWS"),
    output: str | None = typer.Option(None, "--output", "-o", help="Output file (JSON format)"),
    show_all_resources: bool = typer.Option(False, "--all-resources", help="Show all resources, not just idle"),
) -> None:
    """Analyze AWS infrastructure costs and provide optimization recommendations."""
    dashboard = CostDashboard(console)
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    with dashboard.create_progress_context() as progress:
        if demo:
            progress.add_task("Generating demo data...", total=None)
            generator = DemoDataGenerator(monthly_budget=Decimal("5000"), seed=42)
            cost_summary = generator.generate_cost_summary(start_date, end_date)
            resources = generator.generate_resources()
        else:
            task = progress.add_task("Fetching AWS cost data...", total=None)
            try:
                fetcher = AWSFetcher(profile=profile, region=region)
                cost_summary = fetcher.fetch_cost_summary(start_date, end_date)
                progress.update(task, description="Fetching resource data...")
                resources = fetcher.fetch_all_resources()
            except Exception as e:
                console.print(f"[red]Error fetching AWS data: {e}[/red]")
                console.print("[yellow]Tip: Use --demo flag to see sample data[/yellow]")
                raise typer.Exit(1)
        
        progress.update(progress.task_ids[0], description="Analyzing costs...")
        analyzer = CostAnalyzer()
        report = analyzer.analyze(cost_summary, resources)
    
    console.print()
    dashboard.display_analysis_report(report)
    
    if show_all_resources and resources:
        console.print()
        dashboard.display_resources(resources, show_all=True)
    
    if output:
        export_data = {
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "total_cost": str(report.summary.total_cost),
            "efficiency_score": report.efficiency_score,
            "potential_savings": str(report.total_potential_savings),
            "services": [{"name": s.service, "cost": str(s.amount), "percentage": s.percentage} for s in report.summary.by_service],
            "idle_resources": [{"id": r.resource_id, "type": r.resource_type, "monthly_cost": str(r.monthly_cost), "savings": str(r.potential_savings)} for r in report.idle_resources],
            "recommendations": report.recommendations,
        }
        Path(output).write_text(json.dumps(export_data, indent=2))
        console.print(f"\n[green]Report exported to {output}[/green]")


@app.command()
def costs(
    profile: str | None = typer.Option(None, "--profile", "-p", help="AWS profile name"),
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
    demo: bool = typer.Option(False, "--demo", help="Use demo data"),
) -> None:
    """Show cost summary and breakdown by service."""
    dashboard = CostDashboard(console)
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    if demo:
        generator = DemoDataGenerator(seed=42)
        summary = generator.generate_cost_summary(start_date, end_date)
    else:
        try:
            fetcher = AWSFetcher(profile=profile)
            summary = fetcher.fetch_cost_summary(start_date, end_date)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
    
    dashboard.display_summary(summary)
    console.print()
    dashboard.display_service_breakdown(summary)
    console.print()
    dashboard.display_region_breakdown(summary)


@app.command()
def resources(
    profile: str | None = typer.Option(None, "--profile", "-p", help="AWS profile name"),
    region: str = typer.Option("us-east-1", "--region", "-r", help="AWS region"),
    idle_only: bool = typer.Option(True, "--idle-only/--all", help="Show only idle resources"),
    demo: bool = typer.Option(False, "--demo", help="Use demo data"),
) -> None:
    """List AWS resources with cost analysis."""
    dashboard = CostDashboard(console)
    
    if demo:
        generator = DemoDataGenerator(seed=42)
        resource_list = generator.generate_resources()
    else:
        try:
            fetcher = AWSFetcher(profile=profile, region=region)
            resource_list = fetcher.fetch_all_resources()
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
    
    dashboard.display_resources(resource_list, show_all=not idle_only)
    
    total_savings = sum((r.potential_savings for r in resource_list), Decimal("0"))
    if total_savings > 0:
        console.print(f"\n[bold green]Total potential savings: ${total_savings:.2f}/month[/bold green]")


@app.command()
def trends(
    profile: str | None = typer.Option(None, "--profile", "-p", help="AWS profile name"),
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
    demo: bool = typer.Option(False, "--demo", help="Use demo data"),
) -> None:
    """Show cost trends and projections."""
    dashboard = CostDashboard(console)
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    if demo:
        generator = DemoDataGenerator(seed=42)
        summary = generator.generate_cost_summary(start_date, end_date)
    else:
        try:
            fetcher = AWSFetcher(profile=profile)
            summary = fetcher.fetch_cost_summary(start_date, end_date)
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
    
    analyzer = CostAnalyzer()
    report = analyzer.analyze(summary, [])
    
    dashboard.display_summary(summary)
    console.print()
    dashboard._display_trends(report.trends)


@app.command()
def demo_mode() -> None:
    """Run a full demo with realistic sample data."""
    console.print("[bold cyan]Running Infra Cost Sentinel Demo[/bold cyan]\n")
    
    generator = DemoDataGenerator(monthly_budget=Decimal("5000"), seed=42)
    
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    summary = generator.generate_cost_summary(start_date, end_date)
    resources = generator.generate_resources()
    
    analyzer = CostAnalyzer()
    report = analyzer.analyze(summary, resources)
    
    dashboard = CostDashboard(console)
    dashboard.display_analysis_report(report)


def main() -> None:
    app()


if __name__ == "__main__":
    main()

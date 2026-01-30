"""Rich Terminal Dashboard for cost visualization."""

from decimal import Decimal

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from .analyzer import AnalysisReport, CostCategory, TrendDirection
from .models import CostSummary, ResourceCost, ResourceStatus


class CostDashboard:
    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def display_summary(self, summary: CostSummary) -> None:
        title = f"AWS Cost Summary ({summary.start_date} to {summary.end_date})"
        content = self._build_summary_content(summary)
        panel = Panel(content, title=title, border_style="cyan", box=box.ROUNDED)
        self.console.print(panel)

    def _build_summary_content(self, summary: CostSummary) -> Text:
        text = Text()
        text.append("Total Cost: ", style="bold")
        text.append(f"${summary.total_cost:.2f}\n", style="bold green")
        if summary.previous_period_cost:
            text.append("Previous Period: ", style="dim")
            text.append(f"${summary.previous_period_cost:.2f}\n", style="dim")
        if summary.cost_change_percent is not None:
            change = summary.cost_change_percent
            style = "red" if change > 0 else "green"
            sign = "+" if change > 0 else ""
            text.append("Change: ", style="dim")
            text.append(f"{sign}{change:.1f}%\n", style=style)
        text.append("\nProjections:\n", style="bold cyan")
        text.append(f"  Monthly: ${summary.projected_monthly_cost:.2f}\n")
        text.append(f"  Annual:  ${summary.projected_annual_cost:.2f}\n")
        return text

    def display_service_breakdown(self, summary: CostSummary, top_n: int = 10) -> None:
        table = Table(title="Cost by Service", box=box.ROUNDED, header_style="bold cyan")
        table.add_column("Service", style="white")
        table.add_column("Cost", justify="right", style="green")
        table.add_column("Percentage", justify="right")
        table.add_column("Trend", justify="center")
        for service in summary.by_service[:top_n]:
            trend = self._get_service_trend_indicator(service.daily_costs)
            pct_bar = self._create_percentage_bar(service.percentage)
            table.add_row(
                service.service[:40],
                f"${service.amount:.2f}",
                pct_bar,
                trend,
            )
        self.console.print(table)

    def _get_service_trend_indicator(self, daily_costs: list) -> str:
        if not daily_costs or len(daily_costs) < 2:
            return "─"
        first_half = sum((d.amount for d in daily_costs[: len(daily_costs) // 2]), Decimal("0"))
        second_half = sum((d.amount for d in daily_costs[len(daily_costs) // 2 :]), Decimal("0"))
        if second_half > first_half * Decimal("1.1"):
            return "[red]↑[/red]"
        elif second_half < first_half * Decimal("0.9"):
            return "[green]↓[/green]"
        return "[yellow]─[/yellow]"

    def _create_percentage_bar(self, percentage: float, width: int = 20) -> Text:
        filled = int(percentage / 100 * width)
        bar = "█" * filled + "░" * (width - filled)
        text = Text()
        text.append(bar, style="cyan")
        text.append(f" {percentage:.1f}%", style="dim")
        return text

    def display_region_breakdown(self, summary: CostSummary) -> None:
        if not summary.by_region:
            return
        table = Table(title="Cost by Region", box=box.ROUNDED, header_style="bold magenta")
        table.add_column("Region", style="white")
        table.add_column("Cost", justify="right", style="green")
        table.add_column("Percentage", justify="right")
        total = sum(summary.by_region.values())
        for region, cost in sorted(summary.by_region.items(), key=lambda x: x[1], reverse=True):
            pct = float(cost / total * 100) if total > 0 else 0
            pct_bar = self._create_percentage_bar(pct, 15)
            table.add_row(region, f"${cost:.2f}", pct_bar)
        self.console.print(table)

    def display_resources(self, resources: list[ResourceCost], show_all: bool = False) -> None:
        idle = [r for r in resources if r.status == ResourceStatus.IDLE]
        display_resources = resources if show_all else idle
        if not display_resources:
            self.console.print("[green]No idle resources found![/green]")
            return
        title = "All Resources" if show_all else "Idle Resources (Potential Savings)"
        table = Table(title=title, box=box.ROUNDED, header_style="bold yellow")
        table.add_column("Resource ID", style="white")
        table.add_column("Type", style="cyan")
        table.add_column("Region", style="dim")
        table.add_column("Monthly Cost", justify="right", style="red")
        table.add_column("Savings", justify="right", style="green")
        table.add_column("Recommendation")
        for resource in display_resources[:20]:
            status_icon = self._get_status_icon(resource.status)
            rec = (
                resource.recommendation[:30] + "..."
                if resource.recommendation and len(resource.recommendation) > 30
                else (resource.recommendation or "")
            )
            table.add_row(
                f"{status_icon} {resource.resource_id[:20]}",
                resource.resource_type,
                resource.region,
                f"${resource.monthly_cost:.2f}",
                f"${resource.potential_savings:.2f}",
                rec,
            )
        self.console.print(table)
        if len(display_resources) > 20:
            self.console.print(f"[dim]... and {len(display_resources) - 20} more resources[/dim]")

    def _get_status_icon(self, status: ResourceStatus) -> str:
        icons = {
            ResourceStatus.OPTIMAL: "[green]●[/green]",
            ResourceStatus.UNDERUTILIZED: "[yellow]●[/yellow]",
            ResourceStatus.OVERPROVISIONED: "[yellow]●[/yellow]",
            ResourceStatus.IDLE: "[red]●[/red]",
            ResourceStatus.UNKNOWN: "[dim]●[/dim]",
        }
        return icons.get(status, "[dim]●[/dim]")

    def display_analysis_report(self, report: AnalysisReport) -> None:
        self.display_summary(report.summary)
        self.console.print()
        efficiency_style = (
            "green" if report.efficiency_score >= 80 else ("yellow" if report.efficiency_score >= 60 else "red")
        )
        efficiency_text = Text()
        efficiency_text.append("Infrastructure Efficiency Score: ", style="bold")
        efficiency_text.append(f"{report.efficiency_score:.1f}/100", style=f"bold {efficiency_style}")
        self.console.print(Panel(efficiency_text, box=box.ROUNDED))
        if report.alerts:
            self.console.print()
            self._display_alerts(report.alerts)
        if report.trends:
            self.console.print()
            self._display_trends(report.trends)
        self.console.print()
        self.display_service_breakdown(report.summary)
        if report.idle_resources:
            self.console.print()
            self.display_resources(report.idle_resources)
        if report.savings_opportunities:
            self.console.print()
            self._display_savings(report.savings_opportunities, report.total_potential_savings)
        if report.recommendations:
            self.console.print()
            self._display_recommendations(report.recommendations)

    def _display_alerts(self, alerts: list) -> None:
        table = Table(title="Alerts", box=box.ROUNDED, header_style="bold red")
        table.add_column("Severity", style="bold", width=10)
        table.add_column("Alert", style="white")
        table.add_column("Details")
        for alert in alerts:
            severity_style = {"warning": "yellow", "info": "cyan", "critical": "red"}.get(alert.severity, "white")
            table.add_row(
                f"[{severity_style}]{alert.severity.upper()}[/{severity_style}]", alert.title, alert.message[:50]
            )
        self.console.print(table)

    def _display_trends(self, trends: list) -> None:
        table = Table(title="Cost Trends", box=box.ROUNDED, header_style="bold blue")
        table.add_column("Direction", width=10)
        table.add_column("Change", justify="right")
        table.add_column("Period")
        table.add_column("Details")
        for trend in trends[:5]:
            if trend.direction == TrendDirection.UP:
                icon = "[red]↑ UP[/red]"
            elif trend.direction == TrendDirection.DOWN:
                icon = "[green]↓ DOWN[/green]"
            else:
                icon = "[yellow]─ STABLE[/yellow]"
            sign = "+" if trend.change_percent > 0 else ""
            table.add_row(icon, f"{sign}{trend.change_percent:.1f}%", f"{trend.period_days} days", trend.message[:40])
        self.console.print(table)

    def _display_savings(self, opportunities: list, total: Decimal) -> None:
        table = Table(
            title=f"Savings Opportunities (Total: ${total:.2f}/month)", box=box.ROUNDED, header_style="bold green"
        )
        table.add_column("Category", style="cyan")
        table.add_column("Opportunity")
        table.add_column("Savings", justify="right", style="green")
        table.add_column("Effort")
        for opp in sorted(opportunities, key=lambda x: x.potential_savings, reverse=True)[:10]:
            effort_style = {"low": "green", "medium": "yellow", "high": "red"}.get(opp.effort, "white")
            table.add_row(
                opp.category,
                opp.description[:40],
                f"${opp.potential_savings:.2f}",
                f"[{effort_style}]{opp.effort}[/{effort_style}]",
            )
        self.console.print(table)

    def _display_recommendations(self, recommendations: list[str]) -> None:
        text = Text()
        for i, rec in enumerate(recommendations, 1):
            text.append(f"{i}. ", style="bold cyan")
            text.append(f"{rec}\n")
        panel = Panel(text, title="Recommendations", border_style="green", box=box.ROUNDED)
        self.console.print(panel)

    def display_category_breakdown(self, by_category: dict[CostCategory, Decimal]) -> None:
        table = Table(title="Cost by Category", box=box.ROUNDED, header_style="bold cyan")
        table.add_column("Category", style="white")
        table.add_column("Cost", justify="right", style="green")
        table.add_column("Bar", width=30)
        total = sum(by_category.values())
        for category, cost in sorted(by_category.items(), key=lambda x: x[1], reverse=True):
            if cost > 0:
                pct = float(cost / total * 100) if total > 0 else 0
                bar = self._create_percentage_bar(pct, 25)
                table.add_row(category.value.title(), f"${cost:.2f}", bar)
        self.console.print(table)

    def create_progress_context(self) -> Progress:
        return Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=self.console)

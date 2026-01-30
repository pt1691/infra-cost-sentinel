"""Cost Analysis Engine with optimization recommendations."""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from .models import CostSummary, ResourceCost, ResourceStatus


class TrendDirection(Enum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class CostCategory(Enum):
    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    OTHER = "other"


@dataclass
class CostTrend:
    direction: TrendDirection
    change_percent: float
    period_days: int
    message: str


@dataclass
class SavingsOpportunity:
    category: str
    description: str
    potential_savings: Decimal
    effort: str
    resources: list[str]
    recommendation: str


@dataclass
class CostAlert:
    severity: str
    title: str
    message: str
    resource_ids: list[str]
    threshold: Decimal | None = None
    current_value: Decimal | None = None


@dataclass
class AnalysisReport:
    summary: CostSummary
    trends: list[CostTrend]
    alerts: list[CostAlert]
    savings_opportunities: list[SavingsOpportunity]
    idle_resources: list[ResourceCost]
    total_potential_savings: Decimal
    efficiency_score: float
    recommendations: list[str]


class CostAnalyzer:
    SERVICE_CATEGORIES: dict[str, CostCategory] = {
        "Amazon Elastic Compute Cloud": CostCategory.COMPUTE,
        "EC2 - Other": CostCategory.COMPUTE,
        "AWS Lambda": CostCategory.COMPUTE,
        "Amazon Simple Storage Service": CostCategory.STORAGE,
        "Amazon S3": CostCategory.STORAGE,
        "Amazon Elastic Block Store": CostCategory.STORAGE,
        "Amazon Relational Database Service": CostCategory.DATABASE,
        "Amazon RDS": CostCategory.DATABASE,
        "Amazon DynamoDB": CostCategory.DATABASE,
        "Amazon Virtual Private Cloud": CostCategory.NETWORK,
        "Amazon CloudFront": CostCategory.NETWORK,
        "AWS Data Transfer": CostCategory.NETWORK,
    }

    def __init__(self, cost_threshold_percent: float = 20.0, idle_threshold_days: int = 7):
        self.cost_threshold_percent = cost_threshold_percent
        self.idle_threshold_days = idle_threshold_days

    def analyze(self, cost_summary: CostSummary, resources: list[ResourceCost] | None = None) -> AnalysisReport:
        resources = resources or []
        trends = self._analyze_trends(cost_summary)
        alerts = self._generate_alerts(cost_summary, resources)
        idle = self._find_idle_resources(resources)
        savings = self._find_savings_opportunities(cost_summary, resources, idle)
        total_savings = sum((s.potential_savings for s in savings), Decimal("0"))
        total_savings += sum((r.potential_savings for r in idle), Decimal("0"))
        efficiency = self._calculate_efficiency_score(cost_summary, resources, total_savings)
        recommendations = self._generate_recommendations(cost_summary, trends, idle, savings)
        return AnalysisReport(
            summary=cost_summary,
            trends=trends,
            alerts=alerts,
            savings_opportunities=savings,
            idle_resources=idle,
            total_potential_savings=total_savings,
            efficiency_score=efficiency,
            recommendations=recommendations,
        )

    def _analyze_trends(self, summary: CostSummary) -> list[CostTrend]:
        trends: list[CostTrend] = []
        if summary.cost_change_percent is not None:
            change = summary.cost_change_percent
            if change > 5:
                direction = TrendDirection.UP
                message = f"Costs increased by {change:.1f}% compared to previous period"
            elif change < -5:
                direction = TrendDirection.DOWN
                message = f"Costs decreased by {abs(change):.1f}% compared to previous period"
            else:
                direction = TrendDirection.STABLE
                message = "Costs are stable compared to previous period"
            period_days = (summary.end_date - summary.start_date).days
            trends.append(
                CostTrend(direction=direction, change_percent=change, period_days=period_days, message=message)
            )
        for service in summary.by_service[:5]:
            if service.daily_costs and len(service.daily_costs) > 7:
                first_week = sum((d.amount for d in service.daily_costs[:7]), Decimal("0")) / 7
                last_week = sum((d.amount for d in service.daily_costs[-7:]), Decimal("0")) / 7
                if first_week > 0:
                    change = float((last_week - first_week) / first_week * 100)
                    if abs(change) > 10:
                        direction = TrendDirection.UP if change > 0 else TrendDirection.DOWN
                        trends.append(
                            CostTrend(
                                direction=direction,
                                change_percent=change,
                                period_days=7,
                                message=f"{service.service}: {'increased' if change > 0 else 'decreased'} by {abs(change):.1f}%",
                            )
                        )
        return trends

    def _generate_alerts(self, summary: CostSummary, resources: list[ResourceCost]) -> list[CostAlert]:
        alerts: list[CostAlert] = []
        if summary.cost_change_percent and summary.cost_change_percent > self.cost_threshold_percent:
            alerts.append(
                CostAlert(
                    severity="warning",
                    title="Cost Spike Detected",
                    message=f"Costs increased by {summary.cost_change_percent:.1f}% which exceeds {self.cost_threshold_percent}% threshold",
                    resource_ids=[],
                    threshold=Decimal(str(self.cost_threshold_percent)),
                    current_value=Decimal(str(summary.cost_change_percent)),
                )
            )
        idle_resources = [r for r in resources if r.status == ResourceStatus.IDLE]
        if idle_resources:
            idle_cost = sum((r.monthly_cost for r in idle_resources), Decimal("0"))
            alerts.append(
                CostAlert(
                    severity="info",
                    title="Idle Resources Detected",
                    message=f"Found {len(idle_resources)} idle resources costing ${idle_cost:.2f}/month",
                    resource_ids=[r.resource_id for r in idle_resources],
                )
            )
        for service in summary.by_service:
            if service.percentage > 50:
                alerts.append(
                    CostAlert(
                        severity="info",
                        title="High Service Concentration",
                        message=f"{service.service} accounts for {service.percentage:.1f}% of total costs",
                        resource_ids=[],
                    )
                )
                break
        return alerts

    def _find_idle_resources(self, resources: list[ResourceCost]) -> list[ResourceCost]:
        return [r for r in resources if r.status == ResourceStatus.IDLE and r.potential_savings > 0]

    def _find_savings_opportunities(
        self, summary: CostSummary, resources: list[ResourceCost], idle: list[ResourceCost]
    ) -> list[SavingsOpportunity]:
        opportunities: list[SavingsOpportunity] = []
        by_type: dict[str, list[ResourceCost]] = defaultdict(list)
        for r in idle:
            by_type[r.resource_type].append(r)
        for resource_type, items in by_type.items():
            total_savings = sum((r.potential_savings for r in items), Decimal("0"))
            if total_savings > 0:
                opportunities.append(
                    SavingsOpportunity(
                        category=resource_type.split("::")[0],
                        description=f"Clean up {len(items)} idle {resource_type} resources",
                        potential_savings=total_savings,
                        effort="low",
                        resources=[r.resource_id for r in items],
                        recommendation="Review and terminate or snapshot unused resources",
                    )
                )
        ec2_costs = Decimal("0")
        for service in summary.by_service:
            if "EC2" in service.service or "Compute" in service.service:
                ec2_costs += service.amount
        if ec2_costs > Decimal("100"):
            opportunities.append(
                SavingsOpportunity(
                    category="Compute",
                    description="Consider Reserved Instances or Savings Plans for EC2",
                    potential_savings=ec2_costs * Decimal("0.30"),
                    effort="medium",
                    resources=[],
                    recommendation="Analyze usage patterns and commit to 1-year Savings Plans for predictable workloads",
                )
            )
        return opportunities

    def _calculate_efficiency_score(
        self, summary: CostSummary, resources: list[ResourceCost], total_savings: Decimal
    ) -> float:
        if summary.total_cost == 0:
            return 100.0
        waste_ratio = float(total_savings / summary.total_cost)
        idle_ratio = len([r for r in resources if r.status == ResourceStatus.IDLE]) / max(len(resources), 1)
        score = 100.0
        score -= waste_ratio * 40
        score -= idle_ratio * 30
        if summary.cost_change_percent and summary.cost_change_percent > 20:
            score -= min(15, (summary.cost_change_percent - 20) / 2)
        return max(0, min(100, score))

    def _generate_recommendations(
        self, summary: CostSummary, trends: list[CostTrend], idle: list[ResourceCost], savings: list[SavingsOpportunity]
    ) -> list[str]:
        recs: list[str] = []
        if idle:
            total_idle_savings = sum((r.potential_savings for r in idle), Decimal("0"))
            recs.append(f"Clean up {len(idle)} idle resources to save ${total_idle_savings:.2f}/month")
        for trend in trends:
            if trend.direction == TrendDirection.UP and trend.change_percent > 20:
                recs.append(f"Investigate cost increase: {trend.message}")
        for opp in sorted(savings, key=lambda x: x.potential_savings, reverse=True)[:3]:
            if opp.potential_savings > 10:
                recs.append(f"{opp.description} (save ~${opp.potential_savings:.2f}/month)")
        has_savings_plan_rec = any("Savings Plan" in o.description for o in savings)
        if not has_savings_plan_rec and summary.total_cost > Decimal("500"):
            recs.append("Consider AWS Savings Plans for predictable workloads")
        if len(summary.by_region) > 1:
            recs.append("Review multi-region deployment for cost optimization opportunities")
        return recs[:10]

    def categorize_costs(self, summary: CostSummary) -> dict[CostCategory, Decimal]:
        by_category: dict[CostCategory, Decimal] = {cat: Decimal("0") for cat in CostCategory}
        for service in summary.by_service:
            category = self.SERVICE_CATEGORIES.get(service.service, CostCategory.OTHER)
            by_category[category] += service.amount
        return by_category

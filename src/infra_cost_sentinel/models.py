"""Data models for cost analysis."""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class CostCategory(str, Enum):
    """AWS cost categories."""
    COMPUTE = "Compute"
    STORAGE = "Storage"
    DATABASE = "Database"
    NETWORKING = "Networking"
    ANALYTICS = "Analytics"
    MANAGEMENT = "Management"
    SECURITY = "Security"
    OTHER = "Other"


class ResourceStatus(str, Enum):
    """Resource utilization status."""
    OPTIMAL = "optimal"
    UNDERUTILIZED = "underutilized"
    IDLE = "idle"
    OVERPROVISIONED = "overprovisioned"
    RIGHTSIZING_CANDIDATE = "rightsizing_candidate"


class SavingsType(str, Enum):
    """Types of cost savings opportunities."""
    RESERVED_INSTANCES = "reserved_instances"
    SAVINGS_PLANS = "savings_plans"
    SPOT_INSTANCES = "spot_instances"
    RIGHTSIZING = "rightsizing"
    IDLE_RESOURCES = "idle_resources"
    STORAGE_OPTIMIZATION = "storage_optimization"
    DATA_TRANSFER = "data_transfer"
    UNUSED_RESOURCES = "unused_resources"


class Priority(str, Enum):
    """Recommendation priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    
    @property
    def emoji(self) -> str:
        return {
            self.CRITICAL: "🔴",
            self.HIGH: "🟠",
            self.MEDIUM: "🟡",
            self.LOW: "🟢",
        }[self]


class AWSService(str, Enum):
    """Common AWS services."""
    EC2 = "Amazon Elastic Compute Cloud"
    RDS = "Amazon Relational Database Service"
    S3 = "Amazon Simple Storage Service"
    LAMBDA = "AWS Lambda"
    EKS = "Amazon Elastic Kubernetes Service"
    ECS = "Amazon Elastic Container Service"
    DYNAMODB = "Amazon DynamoDB"
    ELASTICACHE = "Amazon ElastiCache"
    REDSHIFT = "Amazon Redshift"
    CLOUDFRONT = "Amazon CloudFront"
    NAT_GATEWAY = "Amazon NAT Gateway"
    EBS = "Amazon Elastic Block Store"
    DATA_TRANSFER = "Data Transfer"
    SECRETS_MANAGER = "AWS Secrets Manager"
    OTHER = "Other"


class DailyCost(BaseModel):
    """Cost data for a single day."""
    date: date
    amount: Decimal
    currency: str = "USD"


class ServiceCost(BaseModel):
    """Cost breakdown for a single AWS service."""
    service: str
    service_code: str
    amount: Decimal
    currency: str = "USD"
    percentage: float = 0.0
    daily_costs: list[DailyCost] = Field(default_factory=list)
    trend_percent: float | None = None
    is_anomaly: bool = False


class ResourceCost(BaseModel):
    """Cost and metadata for a specific AWS resource."""
    resource_id: str
    resource_type: str
    resource_name: str | None = None
    region: str
    account_id: str
    monthly_cost: Decimal
    daily_cost: Decimal
    currency: str = "USD"
    status: ResourceStatus = ResourceStatus.OPTIMAL
    utilization_percent: float | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    created_at: datetime | None = None
    last_used: datetime | None = None
    potential_savings: Decimal = Decimal("0")
    recommendation: str | None = None


class CostRecommendation(BaseModel):
    """A specific cost optimization recommendation."""
    id: str
    title: str
    description: str
    savings_type: SavingsType
    priority: Priority
    estimated_monthly_savings: Decimal
    estimated_annual_savings: Decimal
    confidence: float = 0.8
    affected_resources: list[str] = Field(default_factory=list)
    resource_count: int = 0
    implementation_effort: str = "Medium"
    implementation_steps: list[str] = Field(default_factory=list)
    category: CostCategory = CostCategory.OTHER
    service: str | None = None
    
    def get_roi_score(self) -> float:
        """Calculate ROI score based on savings and effort."""
        effort_multiplier = {"Low": 3.0, "Medium": 2.0, "High": 1.0}.get(self.implementation_effort, 1.0)
        return float(self.estimated_monthly_savings) * effort_multiplier * self.confidence


class CostSummary(BaseModel):
    """Summary of costs for a time period."""
    start_date: date
    end_date: date
    total_cost: Decimal
    currency: str = "USD"
    by_service: list[ServiceCost] = Field(default_factory=list)
    by_region: dict[str, Decimal] = Field(default_factory=dict)
    by_account: dict[str, Decimal] = Field(default_factory=dict)
    previous_period_cost: Decimal | None = None
    cost_change_percent: float | None = None
    projected_monthly_cost: Decimal | None = None
    projected_annual_cost: Decimal | None = None


class CostAnalysis(BaseModel):
    """Complete cost analysis with recommendations."""
    analyzed_at: datetime = Field(default_factory=datetime.now)
    account_id: str
    account_alias: str | None = None
    regions_analyzed: list[str] = Field(default_factory=list)
    summary: CostSummary
    resources: list[ResourceCost] = Field(default_factory=list)
    idle_resources: list[ResourceCost] = Field(default_factory=list)
    underutilized_resources: list[ResourceCost] = Field(default_factory=list)
    recommendations: list[CostRecommendation] = Field(default_factory=list)
    total_potential_monthly_savings: Decimal = Decimal("0")
    total_potential_annual_savings: Decimal = Decimal("0")
    cost_efficiency_score: float = 0.0
    resource_utilization_score: float = 0.0
    optimization_score: float = 0.0
    
    def calculate_scores(self) -> None:
        """Calculate optimization scores based on analysis."""
        self.total_potential_monthly_savings = sum(r.estimated_monthly_savings for r in self.recommendations)
        self.total_potential_annual_savings = self.total_potential_monthly_savings * 12
        
        if self.summary.total_cost > 0:
            savings_ratio = float(self.total_potential_monthly_savings / self.summary.total_cost)
            self.cost_efficiency_score = max(0, min(100, (1 - savings_ratio) * 100))
        
        if self.resources:
            optimal_count = sum(1 for r in self.resources if r.status == ResourceStatus.OPTIMAL)
            self.resource_utilization_score = (optimal_count / len(self.resources)) * 100
        
        self.optimization_score = self.cost_efficiency_score * 0.5 + self.resource_utilization_score * 0.5

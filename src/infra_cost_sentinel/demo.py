"""Demo mode with realistic mock data."""

import random
from datetime import date, timedelta
from decimal import Decimal

from .models import CostSummary, DailyCost, ResourceCost, ResourceStatus, ServiceCost


class DemoDataGenerator:
    SERVICES = [
        ("Amazon Elastic Compute Cloud - Compute", "ec2", 0.35),
        ("Amazon Simple Storage Service", "s3", 0.15),
        ("Amazon Relational Database Service", "rds", 0.20),
        ("AWS Lambda", "lambda", 0.08),
        ("Amazon CloudFront", "cloudfront", 0.05),
        ("Amazon DynamoDB", "dynamodb", 0.07),
        ("AWS Data Transfer", "datatransfer", 0.05),
        ("Amazon Elastic Block Store", "ebs", 0.03),
        ("Amazon Route 53", "route53", 0.02),
    ]

    REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]

    INSTANCE_TYPES = ["t3.micro", "t3.small", "t3.medium", "t3.large", "m5.large", "m5.xlarge", "c5.large"]
    RDS_CLASSES = ["db.t3.micro", "db.t3.small", "db.t3.medium", "db.m5.large"]
    VOLUME_TYPES = ["gp2", "gp3", "io1"]

    def __init__(self, monthly_budget: Decimal = Decimal("5000"), seed: int | None = None):
        self.monthly_budget = monthly_budget
        if seed is not None:
            random.seed(seed)

    def generate_cost_summary(self, start_date: date | None = None, end_date: date | None = None) -> CostSummary:
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        days = (end_date - start_date).days
        self.monthly_budget / 30

        by_service: list[ServiceCost] = []
        total_cost = Decimal("0")

        for service_name, service_code, weight in self.SERVICES:
            service_amount = self.monthly_budget * Decimal(str(weight))
            variation = Decimal(str(random.uniform(0.8, 1.2)))
            service_amount = service_amount * variation * Decimal(str(days)) / 30

            daily_costs: list[DailyCost] = []
            for i in range(days):
                day = start_date + timedelta(days=i)
                day_amount = service_amount / days
                day_variation = Decimal(str(random.uniform(0.7, 1.3)))
                if day.weekday() >= 5:
                    day_variation *= Decimal("0.6")
                daily_costs.append(DailyCost(date=day, amount=day_amount * day_variation))

            actual_amount = sum((d.amount for d in daily_costs), Decimal("0"))
            total_cost += actual_amount

            by_service.append(
                ServiceCost(
                    service=service_name,
                    service_code=service_code,
                    amount=actual_amount,
                    percentage=0,
                    daily_costs=daily_costs,
                )
            )

        for service in by_service:
            service.percentage = float(service.amount / total_cost * 100) if total_cost > 0 else 0
        by_service.sort(key=lambda x: x.amount, reverse=True)

        by_region: dict[str, Decimal] = {}
        remaining = total_cost
        for i, region in enumerate(self.REGIONS):
            if i == len(self.REGIONS) - 1:
                by_region[region] = remaining
            else:
                portion = Decimal(str(random.uniform(0.1, 0.4)))
                amount = total_cost * portion
                by_region[region] = amount
                remaining -= amount

        previous_cost = self.monthly_budget * Decimal(str(random.uniform(0.85, 1.15)))
        cost_change = float((total_cost - previous_cost) / previous_cost * 100) if previous_cost > 0 else 0

        daily_avg = total_cost / days if days > 0 else total_cost
        projected_monthly = daily_avg * 30
        projected_annual = daily_avg * 365

        return CostSummary(
            start_date=start_date,
            end_date=end_date,
            total_cost=total_cost,
            by_service=by_service,
            by_region=by_region,
            previous_period_cost=previous_cost,
            cost_change_percent=cost_change,
            projected_monthly_cost=projected_monthly,
            projected_annual_cost=projected_annual,
        )

    def generate_resources(
        self, num_ec2: int = 8, num_rds: int = 3, num_ebs: int = 12, num_eip: int = 5
    ) -> list[ResourceCost]:
        resources: list[ResourceCost] = []
        resources.extend(self._generate_ec2_instances(num_ec2))
        resources.extend(self._generate_rds_instances(num_rds))
        resources.extend(self._generate_ebs_volumes(num_ebs))
        resources.extend(self._generate_elastic_ips(num_eip))
        return resources

    def _generate_ec2_instances(self, count: int) -> list[ResourceCost]:
        instances: list[ResourceCost] = []
        names = ["web-server", "api-server", "worker", "bastion", "jenkins", "monitoring", "cache", "queue"]

        for i in range(count):
            instance_type = random.choice(self.INSTANCE_TYPES)
            region = random.choice(self.REGIONS)
            is_idle = random.random() < 0.25

            hourly_cost = self._estimate_ec2_hourly_cost(instance_type)
            monthly_cost = hourly_cost * 24 * 30
            daily_cost = hourly_cost * 24

            name = f"{names[i % len(names)]}-{random.randint(1, 99):02d}"
            status = ResourceStatus.IDLE if is_idle else ResourceStatus.OPTIMAL
            savings = monthly_cost * Decimal("0.1") if is_idle else Decimal("0")
            rec = "Terminate or snapshot if not needed" if is_idle else None

            instances.append(
                ResourceCost(
                    resource_id=f"i-{random.randint(10000000, 99999999):08x}",
                    resource_type="EC2::Instance",
                    resource_name=name,
                    region=region,
                    account_id="123456789012",
                    monthly_cost=monthly_cost,
                    daily_cost=daily_cost,
                    status=status,
                    tags={"Name": name, "Environment": random.choice(["prod", "dev", "staging"])},
                    potential_savings=savings,
                    recommendation=rec,
                )
            )
        return instances

    def _generate_rds_instances(self, count: int) -> list[ResourceCost]:
        instances: list[ResourceCost] = []
        names = ["main-db", "analytics-db", "replica", "staging-db", "dev-db"]

        for i in range(count):
            instance_class = random.choice(self.RDS_CLASSES)
            region = random.choice(self.REGIONS)
            is_idle = random.random() < 0.15

            hourly_cost = self._estimate_rds_hourly_cost(instance_class)
            monthly_cost = hourly_cost * 24 * 30
            daily_cost = hourly_cost * 24

            name = names[i % len(names)]
            status = ResourceStatus.IDLE if is_idle else ResourceStatus.OPTIMAL
            savings = monthly_cost * Decimal("0.5") if is_idle else Decimal("0")
            rec = "Consider terminating if not needed" if is_idle else None

            instances.append(
                ResourceCost(
                    resource_id=name,
                    resource_type="RDS::DBInstance",
                    resource_name=name,
                    region=region,
                    account_id="123456789012",
                    monthly_cost=monthly_cost,
                    daily_cost=daily_cost,
                    status=status,
                    potential_savings=savings,
                    recommendation=rec,
                )
            )
        return instances

    def _generate_ebs_volumes(self, count: int) -> list[ResourceCost]:
        volumes: list[ResourceCost] = []

        for _i in range(count):
            volume_type = random.choice(self.VOLUME_TYPES)
            size_gb = random.choice([20, 50, 100, 200, 500, 1000])
            region = random.choice(self.REGIONS)
            is_unattached = random.random() < 0.3

            monthly_cost = self._estimate_ebs_monthly_cost(volume_type, size_gb)
            daily_cost = monthly_cost / 30

            name = f"vol-{random.choice(['data', 'backup', 'logs', 'temp'])}-{random.randint(1, 99):02d}"
            status = ResourceStatus.IDLE if is_unattached else ResourceStatus.OPTIMAL
            savings = monthly_cost if is_unattached else Decimal("0")
            rec = "Unattached volume - consider deleting or snapshotting" if is_unattached else None

            volumes.append(
                ResourceCost(
                    resource_id=f"vol-{random.randint(10000000, 99999999):08x}",
                    resource_type="EC2::Volume",
                    resource_name=name,
                    region=region,
                    account_id="123456789012",
                    monthly_cost=monthly_cost,
                    daily_cost=daily_cost,
                    status=status,
                    tags={"Name": name},
                    potential_savings=savings,
                    recommendation=rec,
                )
            )
        return volumes

    def _generate_elastic_ips(self, count: int) -> list[ResourceCost]:
        eips: list[ResourceCost] = []

        for _i in range(count):
            region = random.choice(self.REGIONS)
            is_unassociated = random.random() < 0.4

            if is_unassociated:
                monthly_cost = Decimal("3.60")
                daily_cost = monthly_cost / 30
                status = ResourceStatus.IDLE
                savings = monthly_cost
                rec = "Unassociated Elastic IP - release if not needed"
            else:
                monthly_cost = Decimal("0")
                daily_cost = Decimal("0")
                status = ResourceStatus.OPTIMAL
                savings = Decimal("0")
                rec = None

            ip = f"{random.randint(1, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"

            eips.append(
                ResourceCost(
                    resource_id=f"eipalloc-{random.randint(10000000, 99999999):08x}",
                    resource_type="EC2::EIP",
                    resource_name=ip,
                    region=region,
                    account_id="123456789012",
                    monthly_cost=monthly_cost,
                    daily_cost=daily_cost,
                    status=status,
                    potential_savings=savings,
                    recommendation=rec,
                )
            )
        return eips

    def _estimate_ec2_hourly_cost(self, instance_type: str) -> Decimal:
        costs = {
            "t3.micro": "0.0104",
            "t3.small": "0.0208",
            "t3.medium": "0.0416",
            "t3.large": "0.0832",
            "m5.large": "0.096",
            "m5.xlarge": "0.192",
            "c5.large": "0.085",
        }
        return Decimal(costs.get(instance_type, "0.10"))

    def _estimate_rds_hourly_cost(self, instance_class: str) -> Decimal:
        costs = {"db.t3.micro": "0.017", "db.t3.small": "0.034", "db.t3.medium": "0.068", "db.m5.large": "0.171"}
        return Decimal(costs.get(instance_class, "0.10"))

    def _estimate_ebs_monthly_cost(self, volume_type: str, size_gb: int) -> Decimal:
        prices = {"gp2": "0.10", "gp3": "0.08", "io1": "0.125"}
        return Decimal(prices.get(volume_type, "0.10")) * Decimal(str(size_gb))

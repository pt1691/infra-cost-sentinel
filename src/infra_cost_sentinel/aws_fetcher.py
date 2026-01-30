"""AWS Cost and Resource Data Fetcher."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from .models import CostSummary, DailyCost, ResourceCost, ResourceStatus, ServiceCost


class AWSFetcher:
    """Fetches cost and resource data from AWS."""

    def __init__(self, profile: str | None = None, region: str = "us-east-1", regions: list[str] | None = None):
        self.profile = profile
        self.primary_region = region
        self.regions = regions or ["us-east-1", "us-west-2"]
        self._session: boto3.Session | None = None

    @property
    def session(self) -> boto3.Session:
        if self._session is None:
            if self.profile:
                self._session = boto3.Session(profile_name=self.profile, region_name=self.primary_region)
            else:
                self._session = boto3.Session(region_name=self.primary_region)
        return self._session

    def get_account_id(self) -> str:
        try:
            sts = self.session.client("sts")
            return sts.get_caller_identity()["Account"]
        except (ClientError, NoCredentialsError):
            return "unknown"

    def get_account_alias(self) -> str | None:
        try:
            iam = self.session.client("iam")
            aliases = iam.list_account_aliases()["AccountAliases"]
            return aliases[0] if aliases else None
        except (ClientError, NoCredentialsError):
            return None

    def fetch_cost_summary(
        self, start_date: date | None = None, end_date: date | None = None, granularity: str = "DAILY"
    ) -> CostSummary:
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        ce = self.session.client("ce", region_name="us-east-1")

        try:
            response = ce.get_cost_and_usage(
                TimePeriod={"Start": start_date.isoformat(), "End": end_date.isoformat()},
                Granularity=granularity,
                Metrics=["UnblendedCost"],
                GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            )
        except ClientError as e:
            raise RuntimeError(f"Failed to fetch cost data: {e}")

        service_totals: dict[str, Decimal] = {}
        service_daily: dict[str, list[DailyCost]] = {}

        for result in response.get("ResultsByTime", []):
            result_date = datetime.strptime(result["TimePeriod"]["Start"], "%Y-%m-%d").date()
            for group in result.get("Groups", []):
                service_name = group["Keys"][0]
                amount = Decimal(group["Metrics"]["UnblendedCost"]["Amount"])
                if service_name not in service_totals:
                    service_totals[service_name] = Decimal("0")
                    service_daily[service_name] = []
                service_totals[service_name] += amount
                service_daily[service_name].append(DailyCost(date=result_date, amount=amount))

        total_cost = sum(service_totals.values())

        by_service: list[ServiceCost] = []
        for service_name, amount in sorted(service_totals.items(), key=lambda x: x[1], reverse=True):
            if amount > Decimal("0.01"):
                percentage = float(amount / total_cost * 100) if total_cost > 0 else 0
                by_service.append(
                    ServiceCost(
                        service=service_name,
                        service_code=service_name.replace(" ", "").lower(),
                        amount=amount,
                        percentage=percentage,
                        daily_costs=service_daily.get(service_name, []),
                    )
                )

        prev_start = start_date - (end_date - start_date)
        prev_end = start_date
        previous_cost: Decimal | None = None
        try:
            prev_response = ce.get_cost_and_usage(
                TimePeriod={"Start": prev_start.isoformat(), "End": prev_end.isoformat()},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
            )
            for result in prev_response.get("ResultsByTime", []):
                prev_amount = Decimal(result["Metrics"]["UnblendedCost"]["Amount"])
                previous_cost = (previous_cost or Decimal("0")) + prev_amount
        except ClientError:
            pass

        cost_change: float | None = None
        if previous_cost and previous_cost > 0:
            cost_change = float((total_cost - previous_cost) / previous_cost * 100)

        by_region: dict[str, Decimal] = {}
        try:
            region_response = ce.get_cost_and_usage(
                TimePeriod={"Start": start_date.isoformat(), "End": end_date.isoformat()},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
                GroupBy=[{"Type": "DIMENSION", "Key": "REGION"}],
            )
            for result in region_response.get("ResultsByTime", []):
                for group in result.get("Groups", []):
                    region = group["Keys"][0] or "global"
                    amount = Decimal(group["Metrics"]["UnblendedCost"]["Amount"])
                    by_region[region] = by_region.get(region, Decimal("0")) + amount
        except ClientError:
            pass

        days_in_period = (end_date - start_date).days
        if days_in_period > 0:
            daily_avg = total_cost / days_in_period
            projected_monthly = daily_avg * 30
            projected_annual = daily_avg * 365
        else:
            projected_monthly = total_cost
            projected_annual = total_cost * 12

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

    def fetch_ec2_resources(self) -> list[ResourceCost]:
        resources: list[ResourceCost] = []
        account_id = self.get_account_id()

        for region in self.regions:
            try:
                ec2 = self.session.client("ec2", region_name=region)
                response = ec2.describe_instances()

                for reservation in response.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        instance_id = instance["InstanceId"]
                        instance_type = instance["InstanceType"]
                        state = instance["State"]["Name"]

                        name = None
                        tags = {}
                        for tag in instance.get("Tags", []):
                            tags[tag["Key"]] = tag["Value"]
                            if tag["Key"] == "Name":
                                name = tag["Value"]

                        if state == "stopped":
                            status = ResourceStatus.IDLE
                        elif state == "running":
                            status = ResourceStatus.OPTIMAL
                        else:
                            status = ResourceStatus.OPTIMAL

                        hourly_cost = self._estimate_ec2_hourly_cost(instance_type)
                        daily_cost = hourly_cost * Decimal("24")
                        monthly_cost = daily_cost * Decimal("30")

                        savings = Decimal("0")
                        recommendation = None
                        if state == "stopped":
                            savings = monthly_cost * Decimal("0.1")
                            recommendation = "Terminate or snapshot if not needed"

                        resources.append(
                            ResourceCost(
                                resource_id=instance_id,
                                resource_type="EC2::Instance",
                                resource_name=name,
                                region=region,
                                account_id=account_id,
                                monthly_cost=monthly_cost,
                                daily_cost=daily_cost,
                                status=status,
                                tags=tags,
                                potential_savings=savings,
                                recommendation=recommendation,
                            )
                        )
            except ClientError:
                continue
        return resources

    def fetch_rds_resources(self) -> list[ResourceCost]:
        resources: list[ResourceCost] = []
        account_id = self.get_account_id()

        for region in self.regions:
            try:
                rds = self.session.client("rds", region_name=region)
                response = rds.describe_db_instances()

                for db in response.get("DBInstances", []):
                    db_id = db["DBInstanceIdentifier"]
                    instance_class = db["DBInstanceClass"]
                    status = db["DBInstanceStatus"]

                    hourly_cost = self._estimate_rds_hourly_cost(instance_class)
                    daily_cost = hourly_cost * Decimal("24")
                    monthly_cost = daily_cost * Decimal("30")

                    resource_status = ResourceStatus.OPTIMAL
                    savings = Decimal("0")
                    recommendation = None

                    if status == "stopped":
                        resource_status = ResourceStatus.IDLE
                        savings = monthly_cost * Decimal("0.5")
                        recommendation = "Consider terminating if not needed"

                    resources.append(
                        ResourceCost(
                            resource_id=db_id,
                            resource_type="RDS::DBInstance",
                            resource_name=db_id,
                            region=region,
                            account_id=account_id,
                            monthly_cost=monthly_cost,
                            daily_cost=daily_cost,
                            status=resource_status,
                            potential_savings=savings,
                            recommendation=recommendation,
                        )
                    )
            except ClientError:
                continue
        return resources

    def fetch_ebs_volumes(self) -> list[ResourceCost]:
        resources: list[ResourceCost] = []
        account_id = self.get_account_id()

        for region in self.regions:
            try:
                ec2 = self.session.client("ec2", region_name=region)
                response = ec2.describe_volumes()

                for volume in response.get("Volumes", []):
                    volume_id = volume["VolumeId"]
                    size_gb = volume["Size"]
                    volume_type = volume["VolumeType"]
                    state = volume["State"]
                    attachments = volume.get("Attachments", [])

                    name = None
                    tags = {}
                    for tag in volume.get("Tags", []):
                        tags[tag["Key"]] = tag["Value"]
                        if tag["Key"] == "Name":
                            name = tag["Value"]

                    monthly_cost = self._estimate_ebs_monthly_cost(volume_type, size_gb)
                    daily_cost = monthly_cost / Decimal("30")

                    resource_status = ResourceStatus.OPTIMAL
                    savings = Decimal("0")
                    recommendation = None

                    if not attachments or state != "in-use":
                        resource_status = ResourceStatus.IDLE
                        savings = monthly_cost
                        recommendation = "Unattached volume - consider deleting or snapshotting"

                    resources.append(
                        ResourceCost(
                            resource_id=volume_id,
                            resource_type="EC2::Volume",
                            resource_name=name,
                            region=region,
                            account_id=account_id,
                            monthly_cost=monthly_cost,
                            daily_cost=daily_cost,
                            status=resource_status,
                            tags=tags,
                            potential_savings=savings,
                            recommendation=recommendation,
                        )
                    )
            except ClientError:
                continue
        return resources

    def fetch_elastic_ips(self) -> list[ResourceCost]:
        resources: list[ResourceCost] = []
        account_id = self.get_account_id()

        for region in self.regions:
            try:
                ec2 = self.session.client("ec2", region_name=region)
                response = ec2.describe_addresses()

                for address in response.get("Addresses", []):
                    allocation_id = address.get("AllocationId", address.get("PublicIp"))
                    public_ip = address.get("PublicIp")
                    association_id = address.get("AssociationId")

                    monthly_cost = Decimal("3.60")
                    daily_cost = monthly_cost / Decimal("30")

                    if association_id:
                        resource_status = ResourceStatus.OPTIMAL
                        savings = Decimal("0")
                        recommendation = None
                        monthly_cost = Decimal("0")
                        daily_cost = Decimal("0")
                    else:
                        resource_status = ResourceStatus.IDLE
                        savings = monthly_cost
                        recommendation = "Unassociated Elastic IP - release if not needed"

                    resources.append(
                        ResourceCost(
                            resource_id=allocation_id or public_ip,
                            resource_type="EC2::EIP",
                            resource_name=public_ip,
                            region=region,
                            account_id=account_id,
                            monthly_cost=monthly_cost,
                            daily_cost=daily_cost,
                            status=resource_status,
                            potential_savings=savings,
                            recommendation=recommendation,
                        )
                    )
            except ClientError:
                continue
        return resources

    def fetch_all_resources(self) -> list[ResourceCost]:
        resources: list[ResourceCost] = []
        resources.extend(self.fetch_ec2_resources())
        resources.extend(self.fetch_rds_resources())
        resources.extend(self.fetch_ebs_volumes())
        resources.extend(self.fetch_elastic_ips())
        return resources

    def _estimate_ec2_hourly_cost(self, instance_type: str) -> Decimal:
        cost_map = {
            "t2.micro": "0.0116",
            "t2.small": "0.023",
            "t2.medium": "0.0464",
            "t2.large": "0.0928",
            "t3.micro": "0.0104",
            "t3.small": "0.0208",
            "t3.medium": "0.0416",
            "t3.large": "0.0832",
            "m5.large": "0.096",
            "m5.xlarge": "0.192",
            "m5.2xlarge": "0.384",
            "c5.large": "0.085",
            "c5.xlarge": "0.17",
            "r5.large": "0.126",
        }
        return Decimal(cost_map.get(instance_type, "0.10"))

    def _estimate_rds_hourly_cost(self, instance_class: str) -> Decimal:
        cost_map = {
            "db.t2.micro": "0.017",
            "db.t2.small": "0.034",
            "db.t2.medium": "0.068",
            "db.t3.micro": "0.017",
            "db.t3.small": "0.034",
            "db.t3.medium": "0.068",
            "db.m5.large": "0.171",
            "db.m5.xlarge": "0.342",
            "db.r5.large": "0.240",
        }
        return Decimal(cost_map.get(instance_class, "0.20"))

    def _estimate_ebs_monthly_cost(self, volume_type: str, size_gb: int) -> Decimal:
        price_map = {
            "gp2": "0.10",
            "gp3": "0.08",
            "io1": "0.125",
            "io2": "0.125",
            "st1": "0.045",
            "sc1": "0.025",
            "standard": "0.05",
        }
        price_per_gb = Decimal(price_map.get(volume_type, "0.10"))
        return price_per_gb * Decimal(str(size_gb))

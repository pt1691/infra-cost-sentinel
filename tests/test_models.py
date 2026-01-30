"""Tests for Infra Cost Sentinel."""

from decimal import Decimal

from infra_cost_sentinel.models import (
    ResourceCost,
    ResourceStatus,
    ServiceCost,
)


class TestServiceCost:
    """Test ServiceCost model."""

    def test_create_service_cost(self):
        """Test creating a service cost."""
        cost = ServiceCost(
            service="Amazon EC2",
            service_code="AmazonEC2",
            amount=Decimal("123.45"),
            percentage=25.5,
        )
        assert cost.service == "Amazon EC2"
        assert cost.amount == Decimal("123.45")
        assert cost.percentage == 25.5


class TestResourceCost:
    """Test ResourceCost model."""

    def test_create_resource_cost(self):
        """Test creating a resource cost."""
        resource = ResourceCost(
            resource_id="i-1234567890abcdef0",
            resource_type="EC2 Instance",
            region="us-west-2",
            account_id="123456789012",
            monthly_cost=Decimal("50.00"),
            daily_cost=Decimal("1.67"),
            status=ResourceStatus.OPTIMAL,
        )
        assert resource.resource_id == "i-1234567890abcdef0"
        assert resource.monthly_cost == Decimal("50.00")

    def test_resource_cost_with_unknown_status(self):
        """Test creating a resource cost with UNKNOWN status."""
        resource = ResourceCost(
            resource_id="i-unknown123",
            resource_type="EC2 Instance",
            region="us-east-1",
            account_id="123456789012",
            monthly_cost=Decimal("100.00"),
            daily_cost=Decimal("3.33"),
            status="unknown",
        )
        assert resource.status == ResourceStatus.UNKNOWN
        assert resource.resource_id == "i-unknown123"

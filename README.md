# 🛡️ Infra Cost Sentinel

> AWS Infrastructure Cost Analyzer with Rich Terminal Dashboards

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Infra Cost Sentinel** is a command-line tool that analyzes your AWS infrastructure costs, identifies savings opportunities, and provides actionable recommendations to optimize your cloud spending.

![Dashboard Screenshot](docs/dashboard.png)

## ✨ Features

- **📊 Cost Analysis Dashboard** - Beautiful Rich terminal UI with cost breakdowns
- **🔍 Resource Scanner** - Finds idle EC2 instances, unattached EBS volumes, unused Elastic IPs
- **🎯 Smart Recommendations** - Actionable optimization suggestions with estimated savings
- **💰 Savings Estimator** - Projects monthly and annual savings potential
- **📈 Trend Analysis** - Compares costs with previous periods
- **🎭 Demo Mode** - Try without AWS credentials using realistic sample data
- **📋 Multiple Output Formats** - Terminal dashboard or JSON for automation

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/praneethturlapati/infra-cost-sentinel.git
cd infra-cost-sentinel

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package
pip install -e .
```

### Try with Demo Data (No AWS Required)

```bash
# Full analysis dashboard with demo data
sentinel scan --demo

# View cost report
sentinel report --demo

# See recommendations
sentinel recommendations --demo

# Find idle resources
sentinel idle --demo
```

### Use with Real AWS Data

```bash
# Configure AWS credentials first
aws configure

# Run full analysis
sentinel scan

# Use specific profile
sentinel scan --profile production

# Scan specific regions
sentinel scan -r us-east-1 -r eu-west-1

# Analyze last 60 days
sentinel scan --days 60
```

## 📋 Requirements

- Python 3.9+
- AWS credentials with the following permissions:
  - `ce:GetCostAndUsage` - Cost Explorer access
  - `ec2:DescribeInstances` - EC2 scanning
  - `ec2:DescribeVolumes` - EBS scanning
  - `ec2:DescribeAddresses` - Elastic IP scanning
  - `rds:DescribeDBInstances` - RDS scanning
  - `sts:GetCallerIdentity` - Account info
  - `iam:ListAccountAliases` - Account alias (optional)

### IAM Policy Example

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ce:GetCostAndUsage",
                "ce:GetCostForecast",
                "ec2:DescribeInstances",
                "ec2:DescribeVolumes",
                "ec2:DescribeAddresses",
                "rds:DescribeDBInstances",
                "sts:GetCallerIdentity",
                "iam:ListAccountAliases"
            ],
            "Resource": "*"
        }
    ]
}
```

## 🛠️ Commands

### `sentinel scan`
Full infrastructure scan with cost analysis and recommendations.

```bash
sentinel scan [OPTIONS]

Options:
  -p, --profile TEXT    AWS profile to use
  -r, --region TEXT     AWS regions to scan (can specify multiple)
  -d, --days INTEGER    Number of days to analyze [default: 30]
  --demo                Use demo data (no AWS credentials required)
  --json                Output results as JSON
```

### `sentinel report`
Cost report without resource scanning (faster).

```bash
sentinel report [OPTIONS]

Options:
  -p, --profile TEXT    AWS profile to use
  -d, --days INTEGER    Number of days to analyze [default: 30]
  --demo                Use demo data
```

### `sentinel recommendations`
Detailed optimization recommendations.

```bash
sentinel recommendations [OPTIONS]

Options:
  -p, --profile TEXT    AWS profile to use
  -r, --region TEXT     AWS regions to scan
  -d, --days INTEGER    Number of days to analyze
  --demo                Use demo data
  -m, --min-savings FLOAT  Minimum monthly savings to show
```

### `sentinel idle`
Find idle and unused resources.

```bash
sentinel idle [OPTIONS]

Options:
  -p, --profile TEXT    AWS profile to use
  -r, --region TEXT     AWS regions to scan
  --demo                Use demo data
```

### `sentinel config`
Show configuration and connection status.

```bash
sentinel config
```

## 📊 What It Detects

### Idle Resources
- ⏹️ **Stopped EC2 Instances** - Still incurring EBS and EIP costs
- 💾 **Unattached EBS Volumes** - Orphaned storage you're paying for
- 🌐 **Unassociated Elastic IPs** - $3.60/month each when not attached

### Cost Optimization Opportunities
- 📦 **Reserved Instances** - Save 30-40% on steady-state workloads
- 💰 **Savings Plans** - Flexible compute discounts up to 66%
- 📉 **Rightsizing** - Overprovisioned resources (coming soon)
- 🔄 **Spot Instances** - For fault-tolerant workloads (coming soon)

## 🏗️ Architecture

```
infra-cost-sentinel/
├── src/infra_cost_sentinel/
│   ├── __init__.py          # Package metadata
│   ├── cli.py                # Typer CLI commands
│   ├── aws_fetcher.py        # boto3 AWS data fetching
│   ├── analyzer.py           # Cost analysis engine
│   ├── dashboard.py          # Rich terminal UI
│   ├── demo.py               # Demo data generator
│   └── models.py             # Pydantic data models
├── tests/
│   └── test_analyzer.py
├── pyproject.toml
├── README.md
└── LICENSE
```

## 🔧 Development

```bash
# Clone and setup
git clone https://github.com/praneethturlapati/infra-cost-sentinel.git
cd infra-cost-sentinel
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
isort src/
```

## 📈 Example Output

```
╔═══════════════════════════════════════════════════════════════╗
║              🛡️  Infra Cost Sentinel  🛡️                      ║
║           AWS Infrastructure Cost Analyzer                     ║
╚═══════════════════════════════════════════════════════════════╝

╭─ 💰 Cost Summary ────────────────────────────────────────────╮
│ 📊 Total Cost       $8,047.20                                │
│ 📅 Period           2024-01-01 to 2024-01-31                 │
│ 📈 vs Previous      ↑ +12.3%                                 │
│ 📆 Projected Annual $96,566.40                               │
╰──────────────────────────────────────────────────────────────╯

╭─ 📈 Optimization Scores ─────────────────────────────────────╮
│ 💰 Cost Efficiency:     ████████████████░░░░ 78%             │
│ 📊 Resource Utilization: ██████████████░░░░░░ 70%            │
│ 🎯 Overall Optimization: ███████████████░░░░░ 74%            │
╰──────────────────────────────────────────────────────────────╯

╭─ 💎 Savings Potential ───────────────────────────────────────╮
│ 💵 Monthly Savings: $2,765.25                                │
│ 💰 Annual Savings: $33,183.00                                │
│ Based on 6 recommendations                                    │
╰──────────────────────────────────────────────────────────────╯
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Rich](https://github.com/Textualize/rich) - Beautiful terminal formatting
- [Typer](https://github.com/tiangolo/typer) - CLI framework
- [Pydantic](https://github.com/pydantic/pydantic) - Data validation
- [boto3](https://github.com/boto/boto3) - AWS SDK for Python

---

**Built with ❤️ for the FinOps and DevOps community**

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, IntEnum
from typing import NamedTuple

from rich.console import Console

console = Console(force_terminal=True)


class RiskSeverity(IntEnum):
    MINIMAL = 0
    LOW = 2
    MODERATE = 3
    HIGH = 5

    @classmethod
    def from_score(cls, score: float) -> "RiskSeverity":
        if score <= 20:
            return cls.LOW
        elif score <= 50:
            return cls.MODERATE
        return cls.HIGH

    def to_string(self) -> str:
        return self.name

    @property
    def emoji(self) -> str:
        emoji_map = {
            RiskSeverity.LOW: "🔵",
            RiskSeverity.MODERATE: "🟡",
            RiskSeverity.HIGH: "🔴",
            RiskSeverity.MINIMAL: "✅",
        }
        return emoji_map[self]


class RiskFactorType(Enum):
    CREATOR_SUPPLY = "Creator Supply"
    CONTRACT_MUTABILITY = "Contract Mutability"
    DEX_SCREENER_PAYMENT = "DexScreener Payment"
    LIQUIDITY = "Liquidity"
    HOLDER_DISTRIBUTION = "Holder Distribution"
    VOLUME_RELATIVE = "Volume Relative"
    CONTRACT_TRANSFER_FEE = "Contract Transfer Fee"
    CONTRACT_FREEZEABLE = "Contract Freezeable"
    AGE = "Age"


@dataclass
class RiskThreshold:
    """Defines thresholds for a risk factor."""

    high: float | None = None
    moderate: float | None = None
    low: float | None = None
    message_template: str = "{value:.1f}% {description}"
    risk_increases_with_value: bool = True

    def get_severity(self, value: float | None) -> RiskSeverity | None:
        """Returns the severity level based on the value and how it relates to risk."""
        if value is None:
            return None

        if self.risk_increases_with_value:
            if self.high is not None and value >= self.high:
                return RiskSeverity.HIGH
            if self.moderate is not None and value >= self.moderate:
                return RiskSeverity.MODERATE
            if self.low is not None and value >= self.low:
                return RiskSeverity.LOW
        else:
            if self.high is not None and value <= self.high:
                return RiskSeverity.HIGH
            if self.moderate is not None and value <= self.moderate:
                return RiskSeverity.MODERATE
            if self.low is not None and value <= self.low:
                return RiskSeverity.LOW

        return None


@dataclass
class RiskAssessmentData:
    """Data structure required for risk assessment"""

    # Creator/Team metrics
    creator_percentage: float | None = None

    # Contract features
    is_metadata_mutable: bool | None = None
    has_transfer_fee: bool | None = None
    is_freezeable: bool | None = None

    # Market metrics
    liquidity_usd: float | None = None
    volume_24h: float | None = None

    # Holder metrics
    top_10_holder_percentage: float | None = None

    # Token age
    creation_time: datetime | None = None

    # DexScreener status
    dex_screener_active_payment: bool | None = None


@dataclass
class RiskFactorDefinition:
    """Defines how to evaluate a specific risk factor"""

    type: RiskFactorType
    description: str
    emoji: str
    threshold: RiskThreshold
    extract_value: Callable[[RiskAssessmentData | None], float | None]
    max_severity: RiskSeverity


# Define all risk factors
RISK_FACTORS = [
    RiskFactorDefinition(
        type=RiskFactorType.CREATOR_SUPPLY,
        description="Creator holds supply",
        emoji="⚠️",
        threshold=RiskThreshold(
            high=30,
            moderate=20,
            low=10,
        ),
        extract_value=lambda data: (
            data.creator_percentage * 100
            if data and data.creator_percentage is not None
            else None
        ),
        max_severity=RiskSeverity.HIGH,
    ),
    RiskFactorDefinition(
        type=RiskFactorType.CONTRACT_MUTABILITY,
        description="Token metadata can be modified after deployment",
        emoji="📝",
        threshold=RiskThreshold(
            moderate=1,
            message_template="{description}",
        ),
        extract_value=lambda data: (
            float(data.is_metadata_mutable)
            if data and data.is_metadata_mutable is not None
            else None
        ),
        max_severity=RiskSeverity.MODERATE,
    ),
    RiskFactorDefinition(
        type=RiskFactorType.DEX_SCREENER_PAYMENT,
        description="Token team hasn't paid for DexScreener listing",
        emoji="📊",
        threshold=RiskThreshold(
            low=1,
            message_template="{description}",
        ),
        extract_value=lambda data: (
            float(not data.dex_screener_active_payment)
            if data and data.dex_screener_active_payment is not None
            else None
        ),
        max_severity=RiskSeverity.LOW,
    ),
    RiskFactorDefinition(
        type=RiskFactorType.LIQUIDITY,
        description="Low liquidity",
        emoji="💧",
        threshold=RiskThreshold(
            high=50000,
            moderate=100000,
            low=200000,
            message_template="Liquidity: ${value:,.0f}",
            risk_increases_with_value=False,
        ),
        extract_value=lambda data: data.liquidity_usd if data else None,
        max_severity=RiskSeverity.HIGH,
    ),
    RiskFactorDefinition(
        type=RiskFactorType.HOLDER_DISTRIBUTION,
        description="Top holders control supply",
        emoji="🎯",
        threshold=RiskThreshold(
            high=40,
            moderate=25,
            low=15,
            message_template="Top 10 holders control {value:.1f}% of total supply",
        ),
        extract_value=lambda data: (
            data.top_10_holder_percentage * 100
            if data and data.top_10_holder_percentage is not None
            else None
        ),
        max_severity=RiskSeverity.HIGH,
    ),
    RiskFactorDefinition(
        type=RiskFactorType.VOLUME_RELATIVE,
        description="Low trading volume relative to liquidity",
        emoji="📉",
        threshold=RiskThreshold(
            moderate=0.05,
            message_template="{description}",
            risk_increases_with_value=False,
        ),
        extract_value=lambda data: (
            data.volume_24h / data.liquidity_usd
            if data
            and data.volume_24h is not None
            and data.liquidity_usd is not None
            and data.liquidity_usd > 0
            else None
        ),
        max_severity=RiskSeverity.MODERATE,
    ),
    RiskFactorDefinition(
        type=RiskFactorType.CONTRACT_TRANSFER_FEE,
        description="Transfer fees enabled",
        emoji="🔒",
        threshold=RiskThreshold(
            moderate=1,
            message_template="{description}",
        ),
        extract_value=lambda data: (
            float(data.has_transfer_fee)
            if data and data.has_transfer_fee is not None
            else None
        ),
        max_severity=RiskSeverity.MODERATE,
    ),
    RiskFactorDefinition(
        type=RiskFactorType.CONTRACT_FREEZEABLE,
        description="Token transfers can be frozen",
        emoji="❄️",
        threshold=RiskThreshold(
            high=1,
            message_template="{description}",
        ),
        extract_value=lambda data: (
            float(data.is_freezeable)
            if data and data.is_freezeable is not None
            else None
        ),
        max_severity=RiskSeverity.HIGH,
    ),
    RiskFactorDefinition(
        type=RiskFactorType.AGE,
        description="Token age",
        emoji="👶",
        threshold=RiskThreshold(
            low=7,
            message_template="{description} ({value:.0f} days)",
            risk_increases_with_value=False,
        ),
        extract_value=lambda data: (
            (datetime.now(UTC) - data.creation_time).days
            if data and data.creation_time is not None
            else float("inf")
        ),
        max_severity=RiskSeverity.LOW,
    ),
]


class RiskFactor(NamedTuple):
    message: str
    severity: RiskSeverity
    emoji: str
    factor_type: RiskFactorType

    @property
    def score(self) -> int:
        return self.severity.value


@dataclass
class RiskScore:
    data: RiskAssessmentData
    total: int = 0
    factors: list[RiskFactor] = field(default_factory=list)

    def __post_init__(self):
        """Evaluates risks after instance initialization"""
        self.evaluate_risk_factors(self.data)

    def evaluate_risk_factors(self, data: RiskAssessmentData) -> None:
        """Evaluates all risk factors for the given assessment data"""
        for factor_def in RISK_FACTORS:
            try:
                value = factor_def.extract_value(data)
                severity = factor_def.threshold.get_severity(value)

                if severity is not None:
                    message = factor_def.threshold.message_template.format(
                        value=value, description=factor_def.description
                    )
                    self.add_factor(
                        message=message,
                        severity=severity,
                        emoji=factor_def.emoji,
                        factor_type=factor_def.type,
                    )
            except Exception as e:
                console.print(f"[red]Error evaluating {factor_def.type}: {e}[/red]")

    def add_factor(
        self,
        message: str,
        severity: RiskSeverity,
        emoji: str,
        factor_type: RiskFactorType,
    ) -> None:
        factor = RiskFactor(message, severity, emoji, factor_type)
        self.factors.append(factor)
        self.total += factor.score

    @property
    def max_possible_score(self) -> int:
        return sum(factor.max_severity.value for factor in RISK_FACTORS)

    @property
    def risk_percentage(self) -> float:
        return (self.total / self.max_possible_score) * 100

    @property
    def risk_level(self) -> RiskSeverity:
        # 1. High risk override
        if self.high_risk_factors:
            return RiskSeverity.HIGH

        # 2. If moderate factors exist, use scoring
        if self.moderate_risk_factors:
            return RiskSeverity.from_score(self.risk_percentage)

        # 3. If only low factors exist, treat as minimal
        if self.low_risk_factors:
            return RiskSeverity.MINIMAL

        # 4. No factors at all
        return RiskSeverity.MINIMAL

    def get_factors_by_severity(self, severity: RiskSeverity) -> list[RiskFactor]:
        """Returns factors for a specific severity level"""
        return [f for f in self.factors if f.severity == severity]

    @property
    def high_risk_factors(self) -> list[RiskFactor]:
        """Returns all high risk factors"""
        return self.get_factors_by_severity(RiskSeverity.HIGH)

    @property
    def moderate_risk_factors(self) -> list[RiskFactor]:
        """Returns all moderate risk factors"""
        return self.get_factors_by_severity(RiskSeverity.MODERATE)

    @property
    def low_risk_factors(self) -> list[RiskFactor]:
        """Returns all low risk factors"""
        return self.get_factors_by_severity(RiskSeverity.LOW)

    @property
    def sorted_factors(self) -> list[RiskFactor]:
        """Returns all factors sorted by severity (HIGH -> MODERATE -> LOW)"""
        return sorted(self.factors, key=lambda x: x.severity.value, reverse=True)

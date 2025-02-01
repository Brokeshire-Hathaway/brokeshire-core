from datetime import datetime
from brokeshire_agents.token_tech_analysis.risk_scoring import RiskAssessmentData
from brokeshire_agents.token_tech_analysis.token_metrics import TokenMetrics


def convert_token_to_risk_data(token_metrics: TokenMetrics) -> RiskAssessmentData:
    """Converts token data to risk assessment data

    Args:
        token_metrics: Token metrics from the token metrics system

    Returns:
        RiskAssessmentData: Data structure containing only the fields needed for risk assessment

    Note:
        This adapter decouples the risk assessment system from the token data structure.
        Any changes to TokenData structure should only require updates to this converter.
    """
    return RiskAssessmentData(
        creator_percentage=(
            float(token_metrics.creator_percentage)
            if token_metrics.creator_percentage
            else None
        ),
        is_metadata_mutable=token_metrics.mutable_metadata,
        has_transfer_fee=token_metrics.transfer_fee_enable,
        is_freezeable=token_metrics.freezeable,
        liquidity_usd=(
            float(token_metrics.liquidity_usd)
            if token_metrics.liquidity_usd is not None
            else None
        ),
        volume_24h=(
            float(token_metrics.volume_24h)
            if token_metrics.volume_24h is not None
            else None
        ),
        top_10_holder_percentage=(
            float(token_metrics.top10_holder_percent)
            if token_metrics.top10_holder_percent is not None
            else None
        ),
        creation_time=token_metrics.creation_time,
        dex_screener_active_payment=any(
            payment.type == "tokenProfile"
            for payment in (token_metrics.dex_screener_payments or [])
        ),
    )

# 왕복 거래 마찰과 본전 승률을 계산하고 전략 아이디어의 통과 여부를 판정한다 (M0, D-013)

from dataclasses import dataclass

# 매도 시 부과되는 세금 합계. 2026년 1월 인상 반영분으로
# 코스피는 증권거래세 0.05% + 농어촌특별세 0.15%, 코스닥은 증권거래세 0.20%다.
# 손실 매도에도 부과되므로 승률과 무관한 고정비로 취급한다 (D-011).
SELL_TAX_PCT = 0.20

# D-012. 손절폭 하한. 이보다 좁으면 고정비인 거래세의 상대 비중이 커져
# 요구 승률이 급등한다. 촘촘히 끊는 쪽이 안전해 보이지만 구조적으로 전략을 죽인다.
MIN_STOP_LOSS_PCT = 1.0

# plan.md 매매 프로파일이 정한 목표 손익비 하한
MIN_REWARD_RISK = 2.0

# D-011. 일 왕복 횟수 상한. 3회 이상은 월 20% 이상을 벌어야 본전이다.
MAX_ROUND_TRIPS_PER_DAY = 2

# 월간 마찰 소모 환산에 쓰는 거래일 수
TRADING_DAYS_PER_MONTH = 20


@dataclass(frozen=True)
class CostModel:
    """왕복 1회에 소모되는 마찰 비용. 모든 단위는 퍼센트(%)다."""

    commission_buy_pct: float
    commission_sell_pct: float
    slippage_round_trip_pct: float
    sell_tax_pct: float = SELL_TAX_PCT

    def __post_init__(self) -> None:
        for name in (
            "commission_buy_pct",
            "commission_sell_pct",
            "slippage_round_trip_pct",
            "sell_tax_pct",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name}는 음수일 수 없다")

    @property
    def round_trip_friction_pct(self) -> float:
        """f = 매수수수료 + 매도수수료 + 거래세 + 슬리피지"""
        return (
            self.commission_buy_pct
            + self.commission_sell_pct
            + self.sell_tax_pct
            + self.slippage_round_trip_pct
        )


def breakeven_win_rate_pct(
    friction_pct: float, stop_loss_pct: float, reward_risk: float
) -> float:
    """본전 승률 p = (f/L + 1) / (R + 1).

    이익 시 R*L 획득에서 마찰 f를 빼고, 손실 시 L 손실에 마찰 f를 더한 뒤
    기대값을 0으로 놓고 p에 대해 푼 결과다.
    """
    if stop_loss_pct <= 0:
        raise ValueError("손절폭은 0보다 커야 한다")
    if reward_risk <= 0:
        raise ValueError("손익비는 0보다 커야 한다")
    if friction_pct < 0:
        raise ValueError("마찰은 음수일 수 없다")
    return (friction_pct / stop_loss_pct + 1) / (reward_risk + 1) * 100


def monthly_friction_pct(
    friction_pct: float,
    round_trips_per_day: float,
    trading_days: int = TRADING_DAYS_PER_MONTH,
) -> float:
    """매회 전량 투입 가정에서 한 달 동안 마찰로 사라지는 비율."""
    if round_trips_per_day < 0:
        raise ValueError("왕복 횟수는 음수일 수 없다")
    if trading_days < 0:
        raise ValueError("거래일 수는 음수일 수 없다")
    return friction_pct * round_trips_per_day * trading_days


@dataclass(frozen=True)
class GateResult:
    passed: bool
    friction_pct: float
    breakeven_win_rate_pct: float
    assumed_win_rate_pct: float
    margin_pp: float
    monthly_friction_pct: float
    violations: tuple[str, ...]


def evaluate(
    cost: CostModel,
    stop_loss_pct: float,
    reward_risk: float,
    round_trips_per_day: float,
    assumed_win_rate_pct: float,
) -> GateResult:
    """전략 아이디어를 문서에 기록된 제약만으로 판정한다.

    임의 기준을 새로 만들지 않는다 (D-009). 판정 근거는 D-011, D-012,
    plan.md의 매매 프로파일, 그리고 본전 승률 비교뿐이다.
    여유(margin)가 충분한지에 대한 최종 판단은 사용자 몫으로 남긴다.
    """
    friction = cost.round_trip_friction_pct
    breakeven = breakeven_win_rate_pct(friction, stop_loss_pct, reward_risk)
    monthly = monthly_friction_pct(friction, round_trips_per_day)

    violations: list[str] = []
    if stop_loss_pct < MIN_STOP_LOSS_PCT:
        violations.append(
            f"손절폭 {stop_loss_pct}%가 하한 {MIN_STOP_LOSS_PCT}% 미만이다 (D-012)"
        )
    if reward_risk < MIN_REWARD_RISK:
        violations.append(
            f"손익비 {reward_risk}:1이 목표 하한 {MIN_REWARD_RISK}:1 미만이다 (plan.md)"
        )
    if round_trips_per_day > MAX_ROUND_TRIPS_PER_DAY:
        violations.append(
            f"일 왕복 {round_trips_per_day}회가 상한 {MAX_ROUND_TRIPS_PER_DAY}회를 초과한다 (D-011)"
        )
    if assumed_win_rate_pct <= breakeven:
        violations.append(
            f"가정 승률 {assumed_win_rate_pct}%가 본전 승률 {breakeven:.1f}% 이하다. 기대값이 마이너스다"
        )

    return GateResult(
        passed=not violations,
        friction_pct=friction,
        breakeven_win_rate_pct=breakeven,
        assumed_win_rate_pct=assumed_win_rate_pct,
        margin_pp=assumed_win_rate_pct - breakeven,
        monthly_friction_pct=monthly,
        violations=tuple(violations),
    )

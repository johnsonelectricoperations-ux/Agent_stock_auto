# 비용 모델이 plan.md와 D-011/D-012에 기록된 수치를 재현하는지 검증한다

import pytest

from costgate.model import (
    CostModel,
    breakeven_win_rate_pct,
    evaluate,
    monthly_friction_pct,
)

# plan.md와 D-011의 표준 시나리오
STANDARD_FRICTION = 0.33


def test_왕복_마찰은_수수료와_거래세와_슬리피지의_합이다():
    cost = CostModel(
        commission_buy_pct=0.015,
        commission_sell_pct=0.015,
        slippage_round_trip_pct=0.10,
    )
    # 0.015 + 0.015 + 0.20(거래세) + 0.10
    assert cost.round_trip_friction_pct == pytest.approx(0.33)


def test_거래세는_기본으로_포함된다():
    cost = CostModel(
        commission_buy_pct=0.0,
        commission_sell_pct=0.0,
        slippage_round_trip_pct=0.0,
    )
    assert cost.round_trip_friction_pct == pytest.approx(0.20)


def test_checklist_M0_검증조건():
    """손절 1.0%, 손익비 2:1, f = 0.33%일 때 요구 승률 44.3%."""
    assert breakeven_win_rate_pct(STANDARD_FRICTION, 1.0, 2.0) == pytest.approx(
        44.3, abs=0.05
    )


@pytest.mark.parametrize(
    "stop_loss,reward_risk,expected",
    [
        # plan.md 및 D-012의 요구 승률 표 (f = 0.33%)
        (0.5, 1.5, 66.4),
        (0.5, 2.0, 55.3),
        (0.5, 3.0, 41.5),
        (1.0, 1.5, 53.2),
        (1.0, 2.0, 44.3),
        (1.0, 3.0, 33.3),
        (2.0, 1.5, 46.6),
        (2.0, 2.0, 38.8),
        (2.0, 3.0, 29.1),
    ],
)
def test_요구_승률_표_재현(stop_loss, reward_risk, expected):
    actual = breakeven_win_rate_pct(STANDARD_FRICTION, stop_loss, reward_risk)
    assert actual == pytest.approx(expected, abs=0.05)


@pytest.mark.parametrize(
    "round_trips,expected",
    # D-011의 월간 마찰 소모 표 (f = 0.33%, 20거래일)
    [(1, 6.6), (2, 13.2), (3, 19.8), (5, 33.0)],
)
def test_월간_마찰_소모_표_재현(round_trips, expected):
    assert monthly_friction_pct(STANDARD_FRICTION, round_trips) == pytest.approx(
        expected, abs=0.05
    )


def test_손절폭을_좁히면_요구_승률이_올라간다():
    """직관과 반대되는 부분이라 회귀 방지용으로 고정한다 (D-012)."""
    넓은_손절 = breakeven_win_rate_pct(STANDARD_FRICTION, 2.0, 2.0)
    좁은_손절 = breakeven_win_rate_pct(STANDARD_FRICTION, 0.5, 2.0)
    assert 좁은_손절 > 넓은_손절


def _standard_cost() -> CostModel:
    return CostModel(
        commission_buy_pct=0.015,
        commission_sell_pct=0.015,
        slippage_round_trip_pct=0.10,
    )


def test_목표_조합은_통과한다():
    """D-012의 목표 조합 — 일 1~2회, 손절 1~2%, 손익비 2:1, 승률 45% 이상."""
    result = evaluate(
        cost=_standard_cost(),
        stop_loss_pct=1.5,
        reward_risk=2.0,
        round_trips_per_day=2,
        assumed_win_rate_pct=45.0,
    )
    assert result.passed
    assert result.violations == ()
    assert result.margin_pp > 0


def test_손절폭_1퍼센트_미만은_탈락한다():
    result = evaluate(
        cost=_standard_cost(),
        stop_loss_pct=0.5,
        reward_risk=2.0,
        round_trips_per_day=1,
        assumed_win_rate_pct=60.0,
    )
    assert not result.passed
    assert any("D-012" in v for v in result.violations)


def test_일_왕복_상한_초과는_탈락한다():
    result = evaluate(
        cost=_standard_cost(),
        stop_loss_pct=1.5,
        reward_risk=2.0,
        round_trips_per_day=3,
        assumed_win_rate_pct=60.0,
    )
    assert not result.passed
    assert any("D-011" in v for v in result.violations)


def test_손익비_미달은_탈락한다():
    result = evaluate(
        cost=_standard_cost(),
        stop_loss_pct=1.5,
        reward_risk=1.5,
        round_trips_per_day=1,
        assumed_win_rate_pct=60.0,
    )
    assert not result.passed
    assert any("손익비" in v for v in result.violations)


def test_본전_승률_이하_가정은_탈락한다():
    result = evaluate(
        cost=_standard_cost(),
        stop_loss_pct=1.0,
        reward_risk=2.0,
        round_trips_per_day=1,
        assumed_win_rate_pct=44.0,  # 본전 44.3% 미만
    )
    assert not result.passed
    assert any("기대값이 마이너스" in v for v in result.violations)


def test_잘못된_입력은_예외를_낸다():
    with pytest.raises(ValueError):
        breakeven_win_rate_pct(STANDARD_FRICTION, 0.0, 2.0)
    with pytest.raises(ValueError):
        breakeven_win_rate_pct(STANDARD_FRICTION, 1.0, 0.0)
    with pytest.raises(ValueError):
        CostModel(
            commission_buy_pct=-0.1,
            commission_sell_pct=0.0,
            slippage_round_trip_pct=0.0,
        )

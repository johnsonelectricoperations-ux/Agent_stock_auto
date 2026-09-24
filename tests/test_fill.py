# 체결 판정이 한국 시장 제약과 비용 모델에 맞는지 검증한다 (D-037)

import pytest

from costgate.model import CostModel
from execution.fill import (
    Bar,
    FillError,
    Order,
    OrderType,
    Side,
    SymbolState,
    simulate_fill,
)

TABLE = [(2_000, 1), (5_000, 5), (20_000, 10), (50_000, 50), (200_000, 1)]

COST = CostModel(
    commission_buy_pct=0.015,
    commission_sell_pct=0.015,
    slippage_round_trip_pct=0.10,
)

NORMAL = SymbolState(halted=False, upper_limit=130_000, lower_limit=70_000)


def _bar(time="0902", open_=100_000, high=101_000, low=99_000, close=100_500):
    return Bar(time=time, open=open_, high=high, low=low, close=close, volume=10_000)


def _market(side=Side.BUY, quantity=1):
    return Order(side=side, order_type=OrderType.MARKET, quantity=quantity)


# ── look-ahead 차단 ──────────────────────────────────────────────


def test_신호_봉에서_체결하면_거부한다():
    """백테스트에서 가장 흔한 버그다. 성과를 조용히 부풀린다."""
    with pytest.raises(FillError) as exc:
        simulate_fill(_market(), "0902", _bar(time="0902"), NORMAL, COST, TABLE)
    assert "look-ahead" in str(exc.value)


def test_신호_봉보다_앞선_봉도_거부한다():
    with pytest.raises(FillError):
        simulate_fill(_market(), "0905", _bar(time="0902"), NORMAL, COST, TABLE)


def test_다음_봉에서는_체결된다():
    result = simulate_fill(_market(), "0901", _bar(time="0902"), NORMAL, COST, TABLE)
    assert result.filled


# ── 한국 시장 제약 ───────────────────────────────────────────────


def test_거래정지_종목은_거부한다():
    halted = SymbolState(halted=True, upper_limit=130_000, lower_limit=70_000)
    result = simulate_fill(_market(), "0901", _bar(), halted, COST, TABLE)
    assert not result.filled
    assert result.reason == "거래정지"


def test_상한가에서_매수는_미체결이다():
    """사려는 쪽만 있고 파는 쪽이 없다. 체결됐다고 처리하면 결과가 무의미해진다."""
    bar = _bar(open_=130_000, high=130_000, low=130_000, close=130_000)
    result = simulate_fill(_market(Side.BUY), "0901", bar, NORMAL, COST, TABLE)
    assert not result.filled
    assert result.reason == "상한가 매수 불가"


def test_상한가에서_매도는_체결된다():
    bar = _bar(open_=130_000, high=130_000, low=130_000, close=130_000)
    result = simulate_fill(_market(Side.SELL), "0901", bar, NORMAL, COST, TABLE)
    assert result.filled


def test_하한가에서_매도는_미체결이다():
    bar = _bar(open_=70_000, high=70_000, low=70_000, close=70_000)
    result = simulate_fill(_market(Side.SELL), "0901", bar, NORMAL, COST, TABLE)
    assert not result.filled
    assert result.reason == "하한가 매도 불가"


def test_하한가에서_매수는_체결된다():
    bar = _bar(open_=70_000, high=70_000, low=70_000, close=70_000)
    result = simulate_fill(_market(Side.BUY), "0901", bar, NORMAL, COST, TABLE)
    assert result.filled


# ── 지정가 ───────────────────────────────────────────────────────


def test_지정가_매수는_저가가_닿아야_체결된다():
    order = Order(Side.BUY, OrderType.LIMIT, 1, limit_price=99_500)
    체결 = simulate_fill(order, "0901", _bar(low=99_000), NORMAL, COST, TABLE)
    assert 체결.filled and 체결.price == 99_500

    미체결 = simulate_fill(order, "0901", _bar(low=99_900), NORMAL, COST, TABLE)
    assert not 미체결.filled
    assert 미체결.reason == "지정가 미도달"


def test_시가가_이미_유리하면_시가에_체결된다():
    order = Order(Side.BUY, OrderType.LIMIT, 1, limit_price=100_500)
    result = simulate_fill(order, "0901", _bar(open_=100_000), NORMAL, COST, TABLE)
    assert result.price == 100_000


def test_지정가에는_슬리피지가_없다():
    """지정가는 그 가격에 못 사면 아예 체결되지 않는다. 밀릴 여지가 없다."""
    order = Order(Side.BUY, OrderType.LIMIT, 1, limit_price=99_500)
    result = simulate_fill(order, "0901", _bar(low=99_000), NORMAL, COST, TABLE)
    assert result.price == result.intended_price


# ── 슬리피지 방향 ────────────────────────────────────────────────


def test_슬리피지는_항상_불리한_쪽이다():
    매수 = simulate_fill(_market(Side.BUY), "0901", _bar(), NORMAL, COST, TABLE)
    매도 = simulate_fill(_market(Side.SELL), "0901", _bar(), NORMAL, COST, TABLE)
    assert 매수.price > 100_000  # 비싸게 산다
    assert 매도.price < 100_000  # 싸게 판다


# ── 동시호가 ─────────────────────────────────────────────────────


def test_동시호가는_종가에_체결된다():
    """단일가 결정 가정. 검증이 필요한 가정이라 테스트로 고정해 둔다."""
    result = simulate_fill(
        _market(Side.SELL), "1519", _bar(time="1520", close=100_500),
        NORMAL, COST, TABLE, closing_auction=True,
    )
    assert result.filled
    assert result.reason == "동시호가 체결"
    assert result.intended_price == 100_500


def test_동시호가에도_상한가_제약은_유효하다():
    bar = _bar(time="1520", open_=130_000, high=130_000, low=130_000, close=130_000)
    result = simulate_fill(
        _market(Side.BUY), "1519", bar, NORMAL, COST, TABLE, closing_auction=True
    )
    assert not result.filled


# ── 비용 모델과의 일치 ───────────────────────────────────────────


def test_실현_마찰이_비용_게이트_예측과_일치한다():
    """체결 엔진과 비용 게이트가 어긋나면 백테스트 전체가 무의미해진다.

    이 테스트가 두 모듈을 묶어 둔다.
    """
    수량 = 100
    기준가 = 100_000
    bar = _bar(open_=기준가, high=기준가, low=기준가, close=기준가)

    매수 = simulate_fill(_market(Side.BUY, 수량), "0901", bar, NORMAL, COST, TABLE)
    매도 = simulate_fill(_market(Side.SELL, 수량), "0901", bar, NORMAL, COST, TABLE)

    마찰 = (
        매수.commission + 매도.commission + 매도.tax + 매수.slippage + 매도.slippage
    )
    원금 = 기준가 * 수량
    실현_마찰률 = 마찰 / 원금 * 100

    assert 실현_마찰률 == pytest.approx(COST.round_trip_friction_pct, abs=0.01)


def test_거래세는_매도에만_붙는다():
    매수 = simulate_fill(_market(Side.BUY), "0901", _bar(), NORMAL, COST, TABLE)
    매도 = simulate_fill(_market(Side.SELL), "0901", _bar(), NORMAL, COST, TABLE)
    assert 매수.tax == 0.0
    assert 매도.tax > 0.0


def test_미체결은_비용이_0이다():
    halted = SymbolState(halted=True, upper_limit=130_000, lower_limit=70_000)
    result = simulate_fill(_market(), "0901", _bar(), halted, COST, TABLE)
    assert result.commission == 0.0
    assert result.tax == 0.0
    assert result.slippage == 0.0


# ── 입력 검증 ────────────────────────────────────────────────────


def test_말이_안_되는_봉을_거부한다():
    with pytest.raises(FillError):
        Bar(time="0902", open=200, high=100, low=50, close=80, volume=1)


def test_수량_0_주문을_거부한다():
    with pytest.raises(FillError):
        Order(Side.BUY, OrderType.MARKET, 0)


def test_가격_없는_지정가를_거부한다():
    with pytest.raises(FillError):
        Order(Side.BUY, OrderType.LIMIT, 1)

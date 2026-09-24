# 주문이 체결됐을지, 얼마에 됐을지 판정한다. 백테스트·페이퍼·섀도가 공유한다 (D-037)

from dataclasses import dataclass
from enum import Enum

from costgate.model import SELL_TAX_PCT, CostModel
from execution.tick import TickTable, round_to_tick

# 왕복 슬리피지의 절반을 편도에 적용한다.
# 비용 모델의 슬리피지는 사고파는 한 바퀴 기준이라 한 번 체결에는 그 절반이 걸린다.
SLIPPAGE_HALVING = 2.0


class FillError(Exception):
    """체결 판정을 할 수 없는 입력일 때 올린다."""


class Side(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"


@dataclass(frozen=True)
class Bar:
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: int

    def __post_init__(self) -> None:
        if not (self.low <= self.open <= self.high):
            raise FillError(f"시가가 고저 범위 밖이다: {self}")
        if not (self.low <= self.close <= self.high):
            raise FillError(f"종가가 고저 범위 밖이다: {self}")


@dataclass(frozen=True)
class SymbolState:
    halted: bool
    upper_limit: float
    lower_limit: float


@dataclass(frozen=True)
class Order:
    side: Side
    order_type: OrderType
    quantity: int
    limit_price: float | None = None

    def __post_init__(self) -> None:
        if self.quantity < 1:
            raise FillError("주문 수량은 1주 이상이어야 한다")
        if self.order_type is OrderType.LIMIT and self.limit_price is None:
            raise FillError("지정가 주문에는 가격이 필요하다")


@dataclass(frozen=True)
class FillResult:
    filled: bool
    reason: str
    intended_price: float | None = None
    price: float | None = None
    quantity: int = 0
    commission: float = 0.0
    tax: float = 0.0

    @property
    def slippage(self) -> float:
        """의도한 가격과 실제 체결가의 차이. 실측 대조에 쓴다 (D-032 원칙 3)."""
        if not self.filled or self.intended_price is None or self.price is None:
            return 0.0
        return abs(self.price - self.intended_price) * self.quantity


def _apply_slippage(price: float, side: Side, cost: CostModel) -> float:
    """항상 불리한 방향으로 민다. 매수는 비싸게, 매도는 싸게."""
    rate = cost.slippage_round_trip_pct / SLIPPAGE_HALVING / 100
    return price * (1 + rate) if side is Side.BUY else price * (1 - rate)


def simulate_fill(
    order: Order,
    signal_time: str,
    execution_bar: Bar,
    state: SymbolState,
    cost: CostModel,
    tick_table: TickTable,
    closing_auction: bool = False,
) -> FillResult:
    """신호가 확정된 뒤의 봉에서 체결을 판정한다.

    체결 봉이 신호 봉보다 뒤여야 한다는 것을 강제한다.
    신호는 봉이 닫혀야 계산되므로, 그 봉의 종가로 체결했다고 처리하면
    이미 지나간 가격에 체결한 것이 되어 look-ahead다.
    백테스트에서 가장 흔한 버그이고, 성과를 조용히 부풀린다.
    """
    if execution_bar.time <= signal_time:
        raise FillError(
            f"체결 봉({execution_bar.time})이 신호 봉({signal_time})보다 뒤여야 한다. "
            "신호가 확정된 봉에서 체결하면 look-ahead다"
        )

    if state.halted:
        return FillResult(filled=False, reason="거래정지")

    # 상한가에서는 사려는 쪽만 있어 매수가 체결되지 않고,
    # 하한가에서는 팔려는 쪽만 있어 매도가 체결되지 않는다.
    if order.side is Side.BUY and execution_bar.open >= state.upper_limit:
        return FillResult(filled=False, reason="상한가 매수 불가")
    if order.side is Side.SELL and execution_bar.open <= state.lower_limit:
        return FillResult(filled=False, reason="하한가 매도 불가")

    if closing_auction:
        # 장 마감 동시호가는 단일가로 결정된다. 해당 봉의 종가를 결정가로 본다.
        # 검증이 필요한 가정이므로 명시해 둔다.
        intended = execution_bar.close
        reason = "동시호가 체결"
    elif order.order_type is OrderType.MARKET:
        intended = execution_bar.open
        reason = "시장가 체결"
    else:
        assert order.limit_price is not None
        limit = order.limit_price
        if order.side is Side.BUY:
            if execution_bar.open <= limit:
                intended = execution_bar.open
            elif execution_bar.low <= limit:
                intended = limit
            else:
                return FillResult(filled=False, reason="지정가 미도달")
        else:
            if execution_bar.open >= limit:
                intended = execution_bar.open
            elif execution_bar.high >= limit:
                intended = limit
            else:
                return FillResult(filled=False, reason="지정가 미도달")
        reason = "지정가 체결"

    # 지정가는 가격이 정해져 있으므로 슬리피지를 걸지 않는다.
    # 슬리피지는 원하는 가격에 못 사는 비용인데, 지정가는 그 경우 아예 체결되지 않는다.
    if order.order_type is OrderType.LIMIT and not closing_auction:
        executed = intended
    else:
        executed = _apply_slippage(intended, order.side, cost)

    executed = round_to_tick(
        executed, tick_table, "up" if order.side is Side.BUY else "down"
    )

    notional = executed * order.quantity
    commission_rate = (
        cost.commission_buy_pct if order.side is Side.BUY else cost.commission_sell_pct
    )
    commission = notional * commission_rate / 100
    tax = notional * SELL_TAX_PCT / 100 if order.side is Side.SELL else 0.0

    return FillResult(
        filled=True,
        reason=reason,
        intended_price=intended,
        price=executed,
        quantity=order.quantity,
        commission=commission,
        tax=tax,
    )

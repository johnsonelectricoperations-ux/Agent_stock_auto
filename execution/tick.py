# 가격을 호가 단위에 맞춘다. 호가에 없는 가격으로 체결됐다고 처리하면 성과가 부풀려진다.

from typing import Sequence


class TickError(Exception):
    """호가 단위 계산이 불가능할 때 올린다."""

# 호가 단위 표는 거래소 규정이고 시장·가격대별로 다르다.
# D-009에 따라 임의 기본값을 넣지 않고 설정에서 받는다.
# 표 형식은 [(상한가격, 호가단위), ...]이며 가격이 상한 미만이면 그 단위를 쓴다.
# 마지막 구간은 상한을 넘는 가격에도 적용된다 (최상단 구간은 무제한).
TickTable = Sequence[tuple[float, float]]


def tick_size(price: float, tick_table: TickTable) -> float:
    """해당 가격대의 호가 단위를 돌려준다."""
    if price < 0:
        raise TickError("가격은 음수일 수 없다")
    if not tick_table:
        raise TickError("호가 단위 표가 비어 있다")

    for bound, size in tick_table:
        if size <= 0:
            raise TickError(f"호가 단위는 0보다 커야 한다: {size}")
        if price < bound:
            return size

    # 최상단 구간은 상한이 없다.
    return tick_table[-1][1]


def round_to_tick(price: float, tick_table: TickTable, direction: str) -> float:
    """가격을 호가 단위에 맞춘다.

    방향은 보수적으로 잡는다. 매수는 올리고 매도는 내려서 항상 불리한 쪽으로 맞춘다.
    유리한 쪽으로 반올림하면 매 체결마다 조금씩 성과가 부풀려지고,
    그 오차가 거래 횟수만큼 누적된다.
    """
    size = tick_size(price, tick_table)
    steps = price / size

    if direction == "up":
        rounded = -(-steps // 1) * size  # 올림
    elif direction == "down":
        rounded = (steps // 1) * size
    elif direction == "nearest":
        rounded = round(steps) * size
    else:
        raise TickError(f"알 수 없는 방향이다: {direction}")

    # 부동소수 오차로 호가에서 미세하게 벗어나는 것을 막는다.
    return round(rounded, 6)

# 체결가가 호가 단위에 맞는지, 반올림이 항상 불리한 쪽인지 검증한다

import pytest

from execution.tick import TickError, round_to_tick, tick_size

# 시험용 표. 실제 표는 거래소 규정을 확인해 설정에 넣는다 (D-009).
TABLE = [(2_000, 1), (5_000, 5), (20_000, 10), (50_000, 50), (200_000, 100)]


@pytest.mark.parametrize(
    "price,expected",
    [(1_500, 1), (2_000, 5), (4_999, 5), (5_000, 10), (19_999, 10), (20_000, 50)],
)
def test_가격대별_호가단위(price, expected):
    assert tick_size(price, TABLE) == expected


def test_최상단_구간은_상한이_없다():
    """표에 적힌 상한을 넘는 가격에도 마지막 구간을 적용한다."""
    assert tick_size(1_000_000, TABLE) == 100


def test_매수는_올림_매도는_내림():
    """유리한 쪽으로 반올림하면 체결마다 성과가 조금씩 부풀려지고 누적된다."""
    assert round_to_tick(10_003, TABLE, "up") == 10_010
    assert round_to_tick(10_003, TABLE, "down") == 10_000


def test_이미_호가에_맞으면_그대로다():
    assert round_to_tick(10_010, TABLE, "up") == 10_010
    assert round_to_tick(10_010, TABLE, "down") == 10_010


def test_반올림_결과는_항상_호가_배수다():
    for price in range(1_000, 30_000, 137):
        for direction in ("up", "down", "nearest"):
            rounded = round_to_tick(price, TABLE, direction)
            assert rounded % tick_size(rounded, TABLE) == 0


def test_잘못된_입력을_거부한다():
    with pytest.raises(TickError):
        tick_size(-1, TABLE)
    with pytest.raises(TickError):
        tick_size(1_000, [])
    with pytest.raises(TickError):
        tick_size(1_000, [(2_000, 0)])
    with pytest.raises(TickError):
        round_to_tick(1_000, TABLE, "옆으로")

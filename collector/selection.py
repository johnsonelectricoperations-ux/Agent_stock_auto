# 관찰 대상을 상위군과 무작위 대조군으로 선정한다. 생존 편향을 막기 위함이다 (D-021)

import random
from dataclasses import dataclass


class SelectionError(Exception):
    """선정 입력이 잘못되었을 때 올린다."""


@dataclass(frozen=True)
class Candidate:
    code: str
    name: str
    change_pct: float
    trading_value: float


@dataclass(frozen=True)
class Selection:
    """어떤 기준으로 누구를 골랐는지 함께 남긴다. 나중에 재현·검증이 가능해야 한다."""

    trade_date: str
    seed: str
    top_by_change: tuple[str, ...]
    top_by_value: tuple[str, ...]
    control: tuple[str, ...]

    @property
    def all_codes(self) -> tuple[str, ...]:
        """수집할 전체 종목. 순서가 안정적이고 중복이 없다."""
        seen: dict[str, None] = {}
        for code in self.top_by_change + self.top_by_value + self.control:
            seen.setdefault(code, None)
        return tuple(seen)


def select_candidates(
    candidates: list[Candidate],
    trade_date: str,
    top_n: int,
    control_n: int,
) -> Selection:
    """상위군과 대조군을 뽑는다.

    대조군이 없으면 분모가 없어 어떤 패턴도 검증되지 않으므로 0을 허용하지 않는다 (D-021).
    같은 날짜로 다시 부르면 대조군까지 완전히 동일하게 나온다. 난수 씨앗을 날짜로 고정해서다.
    """
    if top_n < 1:
        raise SelectionError("상위군은 1종목 이상이어야 한다")
    if control_n < 1:
        raise SelectionError(
            "대조군은 1종목 이상이어야 한다. 대조군 없이는 생존 편향을 막을 수 없다 (D-021)"
        )

    codes = [candidate.code for candidate in candidates]
    duplicates = {code for code in codes if codes.count(code) > 1}
    if duplicates:
        raise SelectionError(f"입력에 중복 종목이 있다: {sorted(duplicates)}")

    # 동점일 때 순서가 흔들리면 재현이 깨지므로 종목코드로 2차 정렬한다.
    by_change = sorted(candidates, key=lambda c: (-c.change_pct, c.code))
    by_value = sorted(candidates, key=lambda c: (-c.trading_value, c.code))

    top_by_change = tuple(c.code for c in by_change[:top_n])
    top_by_value = tuple(c.code for c in by_value[:top_n])

    chosen = set(top_by_change) | set(top_by_value)
    pool = sorted(code for code in codes if code not in chosen)

    rng = random.Random(trade_date)
    control = tuple(sorted(rng.sample(pool, min(control_n, len(pool)))))

    return Selection(
        trade_date=trade_date,
        seed=trade_date,
        top_by_change=top_by_change,
        top_by_value=top_by_value,
        control=control,
    )

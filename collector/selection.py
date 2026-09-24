# 분봉·호가 수집 대상을 상위군·대조군·고정 코호트로 선정한다 (D-032, D-033)

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
    """어떤 기준으로 누구를 골랐는지 함께 남긴다. 나중에 재현·검증이 가능해야 한다.

    이 선정은 장 마감 후에 결과를 보고 이뤄지는 C층 선정이다 (D-033).
    여기서 모은 데이터는 분석 재료이지 진입 조건이 아니다.
    진입 조건에 그대로 쓰면 '장 마감 후에야 알 수 있는 것'을 장중에 안다고
    가정하는 셈이 되어, 백테스트만 되고 실전에서는 재현되지 않는 규칙이 나온다.
    """

    trade_date: str
    seed: str
    top_by_change: tuple[str, ...]
    top_by_value: tuple[str, ...]
    control: tuple[str, ...]
    cohort: tuple[str, ...]
    cohort_missing: tuple[str, ...]

    @property
    def all_codes(self) -> tuple[str, ...]:
        """수집할 전체 종목. 순서가 안정적이고 중복이 없다."""
        seen: dict[str, None] = {}
        for code in self.top_by_change + self.top_by_value + self.control + self.cohort:
            seen.setdefault(code, None)
        return tuple(seen)


def draw_cohort(candidates: list[Candidate], size: int, seed: str) -> tuple[str, ...]:
    """고정 코호트를 최초 1회 뽑는다. 이후로는 저장된 것을 계속 쓴다.

    매일 새로 뽑는 대조군은 분모 역할은 하지만 시계열이 끊겨 기준선이 되지 못한다.
    "이 종목의 평소"를 알아야 "오늘이 특이한지"를 판단할 수 있고,
    그러려면 같은 종목을 계속 추적해야 한다.

    빨리 뽑을수록 기준선이 길게 쌓이므로 수집 첫날에 뽑는다.
    """
    if size < 1:
        raise SelectionError("고정 코호트는 1종목 이상이어야 한다")

    codes = sorted(candidate.code for candidate in candidates)
    if not codes:
        raise SelectionError("후보가 비어 있어 코호트를 뽑을 수 없다")

    rng = random.Random(seed)
    return tuple(sorted(rng.sample(codes, min(size, len(codes)))))


def select_candidates(
    candidates: list[Candidate],
    trade_date: str,
    top_n: int,
    control_n: int,
    cohort: tuple[str, ...],
) -> Selection:
    """상위군·대조군을 뽑고 고정 코호트를 합쳐 당일 수집 대상을 만든다.

    대조군이 없으면 분모가 없어 에이전트가 생존 편향에 빠진 규칙을 만들어낸다 (D-032).
    고정 코호트가 없으면 기준선이 없어 무엇이 특이한지 판단할 수 없다 (D-033).
    둘 다 비우는 것을 허용하지 않는다.

    같은 날짜로 다시 부르면 대조군까지 완전히 동일하게 나온다. 난수 씨앗을 날짜로 고정해서다.
    """
    if top_n < 1:
        raise SelectionError("상위군은 1종목 이상이어야 한다")
    if control_n < 1:
        raise SelectionError(
            "대조군은 1종목 이상이어야 한다. 대조군 없이는 생존 편향을 막을 수 없다 (D-032)"
        )
    if not cohort:
        raise SelectionError(
            "고정 코호트를 먼저 뽑아야 한다. 기준선 없이는 특이값을 판단할 수 없다 (D-033)"
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

    available = set(codes)
    # 상장폐지·거래정지로 빠진 코호트는 기록만 하고 대체하지 않는다.
    # 대체하면 살아남은 종목만 남아 또 생존 편향이 생긴다.
    cohort_present = tuple(code for code in cohort if code in available)
    cohort_missing = tuple(code for code in cohort if code not in available)

    chosen = set(top_by_change) | set(top_by_value) | set(cohort_present)
    pool = sorted(code for code in codes if code not in chosen)

    rng = random.Random(trade_date)
    control = tuple(sorted(rng.sample(pool, min(control_n, len(pool)))))

    return Selection(
        trade_date=trade_date,
        seed=trade_date,
        top_by_change=top_by_change,
        top_by_value=top_by_value,
        control=control,
        cohort=cohort_present,
        cohort_missing=cohort_missing,
    )

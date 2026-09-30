# 수집 대상을 예산 안에서 선정한다. 고정 몫은 사람이, 재량 몫은 에이전트가 정한다 (D-032, D-033, D-039)

import random
from dataclasses import dataclass, field


class SelectionError(Exception):
    """선정 입력이 예산이나 고정 몫 규칙을 어길 때 올린다."""


@dataclass(frozen=True)
class Candidate:
    code: str
    name: str
    change_pct: float
    trading_value: float


@dataclass(frozen=True)
class CollectBudget:
    """사람이 정하는 울타리. 에이전트가 바꿀 수 없다 (D-039).

    D-031에서 "규칙은 자율, 한도는 사람"으로 정한 것과 같은 구조다.
    수집에서도 무엇을 모을지는 에이전트가 정하되, 얼마나 모을지와
    분모·기준선을 얼마나 확보할지는 사람이 정한다.
    """

    max_symbols: int
    min_control: int
    min_cohort: int
    min_exploration: int

    def __post_init__(self) -> None:
        for name in ("min_control", "min_cohort", "min_exploration"):
            if getattr(self, name) < 1:
                raise SelectionError(
                    f"{name}은 1 이상이어야 한다. 고정 몫을 0으로 두면 방어선이 사라진다 (D-039)"
                )
        if self.max_symbols < 1:
            raise SelectionError("max_symbols는 1 이상이어야 한다")


@dataclass(frozen=True)
class CollectPlan:
    """재량 몫 배분. 지금은 설정에서 오고, 나중에 에이전트가 예산 안에서 제안한다.

    exploration_codes는 에이전트가 "이런 종목이 궁금하다"고 지정한 목록이다.
    부족한 만큼은 무작위로 채운다. 에이전트가 없는 동안에는 전부 무작위가 된다.
    """

    top_n: int
    control_n: int
    exploration_n: int
    exploration_codes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Selection:
    """어떤 기준으로 누구를 골랐는지 함께 남긴다. 나중에 재현·검증이 가능해야 한다.

    이 선정은 장 마감 후에 결과를 보고 이뤄지는 C층 선정이다 (D-033).
    여기서 모은 데이터는 분석 재료이지 진입 조건이 아니다.
    """

    trade_date: str
    seed: str
    top_by_change: tuple[str, ...]
    top_by_value: tuple[str, ...]
    control: tuple[str, ...]
    cohort: tuple[str, ...]
    cohort_missing: tuple[str, ...]
    exploration: tuple[str, ...]

    @property
    def all_codes(self) -> tuple[str, ...]:
        """수집할 전체 종목. 순서가 안정적이고 중복이 없다."""
        seen: dict[str, None] = {}
        groups = (
            self.top_by_change
            + self.top_by_value
            + self.cohort
            + self.exploration
            + self.control
        )
        for code in groups:
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


def _sample(pool: list[str], count: int, seed: str) -> tuple[str, ...]:
    rng = random.Random(seed)
    return tuple(sorted(rng.sample(pool, min(count, len(pool)))))


def select_candidates(
    candidates: list[Candidate],
    trade_date: str,
    plan: CollectPlan,
    budget: CollectBudget,
    cohort: tuple[str, ...],
) -> Selection:
    """예산 안에서 당일 수집 대상을 만든다.

    고정 몫(대조군·코호트·탐색 슬롯)이 예산의 최소선을 채우는지 먼저 검사한다.
    에이전트가 "효율적이지 않다"며 분모나 기준선을 줄이는 것을 막기 위함이다.
    탐색 슬롯이 없으면 에이전트는 이미 쓸모를 아는 데이터 안에서만 조합하게 된다.

    같은 날짜로 다시 부르면 무작위 부분까지 완전히 동일하게 나온다.
    """
    if plan.top_n < 1:
        raise SelectionError("상위군은 1종목 이상이어야 한다")
    if plan.control_n < budget.min_control:
        raise SelectionError(
            f"대조군 {plan.control_n}이 고정 몫 최소 {budget.min_control} 미만이다. "
            "대조군 없이는 생존 편향을 막을 수 없다 (D-032)"
        )
    if plan.exploration_n < budget.min_exploration:
        raise SelectionError(
            f"탐색 슬롯 {plan.exploration_n}이 고정 몫 최소 {budget.min_exploration} 미만이다. "
            "탐색 없이는 이미 아는 것 안에서만 조합하게 된다 (D-039)"
        )
    if len(cohort) < budget.min_cohort:
        raise SelectionError(
            f"고정 코호트 {len(cohort)}가 최소 {budget.min_cohort} 미만이다. "
            "기준선 없이는 특이값을 판단할 수 없다 (D-033)"
        )

    codes = [candidate.code for candidate in candidates]
    duplicates = {code for code in codes if codes.count(code) > 1}
    if duplicates:
        raise SelectionError(f"입력에 중복 종목이 있다: {sorted(duplicates)}")

    available = set(codes)

    # 동점일 때 순서가 흔들리면 재현이 깨지므로 종목코드로 2차 정렬한다.
    by_change = sorted(candidates, key=lambda c: (-c.change_pct, c.code))
    by_value = sorted(candidates, key=lambda c: (-c.trading_value, c.code))

    top_by_change = tuple(c.code for c in by_change[: plan.top_n])
    top_by_value = tuple(c.code for c in by_value[: plan.top_n])

    # 상장폐지·거래정지로 빠진 코호트는 기록만 하고 대체하지 않는다.
    # 대체하면 살아남은 종목만 남아 또 생존 편향이 생긴다.
    cohort_present = tuple(code for code in cohort if code in available)
    cohort_missing = tuple(code for code in cohort if code not in available)

    taken = set(top_by_change) | set(top_by_value) | set(cohort_present)

    # 탐색 슬롯은 에이전트 지정을 먼저 쓰고, 모자란 만큼 무작위로 채운다.
    requested = tuple(
        code for code in plan.exploration_codes if code in available and code not in taken
    )
    exploration = requested[: plan.exploration_n]
    taken |= set(exploration)
    shortfall = plan.exploration_n - len(exploration)
    if shortfall > 0:
        pool = sorted(code for code in codes if code not in taken)
        exploration += _sample(pool, shortfall, f"{trade_date}-exploration")
        taken |= set(exploration)

    pool = sorted(code for code in codes if code not in taken)
    control = _sample(pool, plan.control_n, trade_date)

    selection = Selection(
        trade_date=trade_date,
        seed=trade_date,
        top_by_change=top_by_change,
        top_by_value=top_by_value,
        control=control,
        cohort=cohort_present,
        cohort_missing=cohort_missing,
        exploration=tuple(sorted(exploration)),
    )

    total = len(selection.all_codes)
    if total > budget.max_symbols:
        raise SelectionError(
            f"수집 대상 {total}종목이 예산 {budget.max_symbols}를 초과한다. "
            "재량 몫(top_n, control_n, exploration_n)을 줄여야 한다"
        )

    return selection

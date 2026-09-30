# 수집 예산 안에서 고정 몫이 지켜지고 선정이 재현 가능한지 검증한다 (D-032, D-033, D-039)

import pytest

from collector.selection import (
    Candidate,
    CollectBudget,
    CollectPlan,
    SelectionError,
    draw_cohort,
    select_candidates,
)


def _candidates(count: int) -> list[Candidate]:
    """등락률과 거래대금이 서로 다른 순서가 되도록 만든다."""
    return [
        Candidate(
            code=f"{index:06d}",
            name=f"종목{index}",
            change_pct=float(index),
            trading_value=float(count - index),
        )
        for index in range(count)
    ]


COHORT = ("000030", "000031", "000032")
BUDGET = CollectBudget(max_symbols=100, min_control=2, min_cohort=3, min_exploration=2)
PLAN = CollectPlan(top_n=3, control_n=5, exploration_n=4)


def _select(count=60, date="2026-09-21", plan=PLAN, budget=BUDGET, cohort=COHORT):
    return select_candidates(_candidates(count), date, plan, budget, cohort)


# ── 그룹별 선정 ──────────────────────────────────────────────────


def test_상위군은_등락률과_거래대금_각각_뽑는다():
    selection = _select()
    assert selection.top_by_change == ("000059", "000058", "000057")
    assert selection.top_by_value == ("000000", "000001", "000002")


def test_그룹끼리_겹치지_않는다():
    selection = _select()
    그룹들 = [
        set(selection.top_by_change) | set(selection.top_by_value),
        set(selection.cohort),
        set(selection.exploration),
        set(selection.control),
    ]
    합계 = sum(len(g) for g in 그룹들)
    assert len(set().union(*그룹들)) == 합계


def test_전체_목록에_중복이_없다():
    selection = _select()
    assert len(selection.all_codes) == len(set(selection.all_codes))


# ── 재현성 ───────────────────────────────────────────────────────


def test_같은_날짜면_완전히_같다():
    """재현 불가능한 표본은 검증에 쓸 수 없다."""
    assert _select() == _select()


def test_날짜가_다르면_무작위_부분이_달라진다():
    first = _select(date="2026-09-21")
    second = _select(date="2026-09-22")
    assert first.control != second.control
    assert first.exploration != second.exploration


def test_코호트는_날짜가_바뀌어도_같다():
    """기준선 역할을 하려면 시계열이 끊기지 않아야 한다 (D-033)."""
    assert _select(date="2026-09-21").cohort == _select(date="2026-09-22").cohort


def test_동점이어도_순서가_흔들리지_않는다():
    tied = [
        Candidate(code=f"{i:06d}", name=f"종목{i}", change_pct=5.0, trading_value=5.0)
        for i in range(40)
    ]
    first = select_candidates(tied, "2026-09-21", PLAN, BUDGET, COHORT)
    second = select_candidates(list(reversed(tied)), "2026-09-21", PLAN, BUDGET, COHORT)
    assert first == second


# ── 고정 몫 방어 (D-039) ─────────────────────────────────────────


def test_대조군이_고정_몫_미만이면_거부한다():
    plan = CollectPlan(top_n=3, control_n=1, exploration_n=4)
    with pytest.raises(SelectionError) as exc:
        _select(plan=plan)
    assert "D-032" in str(exc.value)


def test_탐색_슬롯이_고정_몫_미만이면_거부한다():
    """탐색이 없으면 에이전트는 이미 아는 것 안에서만 조합하게 된다."""
    plan = CollectPlan(top_n=3, control_n=5, exploration_n=1)
    with pytest.raises(SelectionError) as exc:
        _select(plan=plan)
    assert "D-039" in str(exc.value)


def test_코호트가_고정_몫_미만이면_거부한다():
    with pytest.raises(SelectionError) as exc:
        _select(cohort=("000030",))
    assert "D-033" in str(exc.value)


def test_고정_몫_최소를_0으로_둘_수_없다():
    """에이전트가 방어선을 0으로 만드는 것을 예산 수준에서 막는다."""
    with pytest.raises(SelectionError) as exc:
        CollectBudget(max_symbols=100, min_control=0, min_cohort=3, min_exploration=2)
    assert "D-039" in str(exc.value)


# ── 예산 상한 ────────────────────────────────────────────────────


def test_예산을_초과하면_거부한다():
    좁은_예산 = CollectBudget(
        max_symbols=5, min_control=2, min_cohort=3, min_exploration=2
    )
    with pytest.raises(SelectionError) as exc:
        _select(budget=좁은_예산)
    assert "예산" in str(exc.value)


def test_예산_안이면_통과한다():
    selection = _select()
    assert len(selection.all_codes) <= BUDGET.max_symbols


# ── 탐색 슬롯 (D-039) ────────────────────────────────────────────


def test_에이전트_지정을_먼저_쓴다():
    plan = CollectPlan(
        top_n=3, control_n=5, exploration_n=4,
        exploration_codes=("000040", "000041"),
    )
    selection = _select(plan=plan)
    assert "000040" in selection.exploration
    assert "000041" in selection.exploration


def test_지정이_모자라면_무작위로_채운다():
    plan = CollectPlan(
        top_n=3, control_n=5, exploration_n=4, exploration_codes=("000040",)
    )
    selection = _select(plan=plan)
    assert len(selection.exploration) == 4


def test_지정이_넘치면_슬롯_크기까지만_쓴다():
    plan = CollectPlan(
        top_n=3, control_n=5, exploration_n=2,
        exploration_codes=("000040", "000041", "000042", "000043"),
    )
    selection = _select(plan=plan)
    assert len(selection.exploration) == 2


def test_지정이_없으면_전부_무작위다():
    """에이전트가 없는 동안에는 탐색 슬롯이 무작위로 채워진다."""
    selection = _select()
    assert len(selection.exploration) == PLAN.exploration_n


def test_이미_뽑힌_종목은_탐색_지정에서_제외된다():
    plan = CollectPlan(
        top_n=3, control_n=5, exploration_n=4,
        exploration_codes=("000059", "000030"),  # 상위군, 코호트
    )
    selection = _select(plan=plan)
    assert "000059" not in selection.exploration
    assert "000030" not in selection.exploration


# ── 코호트 결손 ──────────────────────────────────────────────────


def test_사라진_코호트는_기록되고_대체되지_않는다():
    """대체하면 살아남은 종목만 남아 생존 편향이 생긴다 (D-033)."""
    selection = _select(cohort=COHORT + ("999999",))
    assert selection.cohort_missing == ("999999",)
    assert "999999" not in selection.all_codes
    assert len(selection.cohort) == 3


# ── 입력 검증 ────────────────────────────────────────────────────


def test_상위군_0은_거부한다():
    with pytest.raises(SelectionError):
        _select(plan=CollectPlan(top_n=0, control_n=5, exploration_n=4))


def test_중복_종목_입력을_거부한다():
    duplicated = _candidates(40) + [_candidates(40)[0]]
    with pytest.raises(SelectionError) as exc:
        select_candidates(duplicated, "2026-09-21", PLAN, BUDGET, COHORT)
    assert "중복" in str(exc.value)


# ── 코호트 추첨 ──────────────────────────────────────────────────


def test_코호트_추첨은_같은_씨앗이면_같다():
    first = draw_cohort(_candidates(100), size=10, seed="cohort-2026")
    second = draw_cohort(_candidates(100), size=10, seed="cohort-2026")
    assert first == second
    assert len(first) == 10


def test_코호트_추첨은_씨앗이_다르면_달라진다():
    assert draw_cohort(_candidates(100), 10, "a") != draw_cohort(_candidates(100), 10, "b")


def test_코호트_추첨_잘못된_입력을_거부한다():
    with pytest.raises(SelectionError):
        draw_cohort(_candidates(100), size=0, seed="s")
    with pytest.raises(SelectionError):
        draw_cohort([], size=10, seed="s")

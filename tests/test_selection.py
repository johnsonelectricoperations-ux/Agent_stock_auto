# 대조군이 생존 편향을 막는지, 코호트가 기준선이 되는지, 선정이 재현 가능한지 검증한다 (D-032, D-033)

import pytest

from collector.selection import (
    Candidate,
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


def test_상위군은_등락률과_거래대금_각각_뽑는다():
    selection = select_candidates(
        _candidates(40), "2026-09-21", top_n=3, control_n=3, cohort=COHORT
    )
    # 등락률은 index가 클수록 높다
    assert selection.top_by_change == ("000039", "000038", "000037")
    # 거래대금은 index가 작을수록 크다
    assert selection.top_by_value == ("000000", "000001", "000002")


def test_대조군은_상위군_코호트와_겹치지_않는다():
    selection = select_candidates(
        _candidates(40), "2026-09-21", top_n=5, control_n=5, cohort=COHORT
    )
    이미_수집 = (
        set(selection.top_by_change) | set(selection.top_by_value) | set(selection.cohort)
    )
    assert not (set(selection.control) & 이미_수집)


def test_같은_날짜면_대조군까지_완전히_같다():
    """재현 불가능한 표본은 검증에 쓸 수 없다."""
    first = select_candidates(
        _candidates(50), "2026-09-21", top_n=3, control_n=7, cohort=COHORT
    )
    second = select_candidates(
        _candidates(50), "2026-09-21", top_n=3, control_n=7, cohort=COHORT
    )
    assert first == second


def test_날짜가_다르면_대조군이_달라진다():
    first = select_candidates(
        _candidates(50), "2026-09-21", top_n=3, control_n=7, cohort=COHORT
    )
    second = select_candidates(
        _candidates(50), "2026-09-22", top_n=3, control_n=7, cohort=COHORT
    )
    assert first.control != second.control


def test_코호트는_날짜가_바뀌어도_같다():
    """기준선 역할을 하려면 시계열이 끊기지 않아야 한다 (D-033)."""
    first = select_candidates(
        _candidates(50), "2026-09-21", top_n=3, control_n=7, cohort=COHORT
    )
    second = select_candidates(
        _candidates(50), "2026-09-22", top_n=3, control_n=7, cohort=COHORT
    )
    assert first.cohort == second.cohort == COHORT


def test_사라진_코호트는_기록되고_대체되지_않는다():
    """대체하면 살아남은 종목만 남아 생존 편향이 생긴다 (D-033)."""
    상장폐지_포함 = COHORT + ("999999",)
    selection = select_candidates(
        _candidates(50), "2026-09-21", top_n=3, control_n=7, cohort=상장폐지_포함
    )
    assert selection.cohort_missing == ("999999",)
    assert "999999" not in selection.all_codes
    assert len(selection.cohort) == 3  # 빈자리를 다른 종목으로 채우지 않는다


def test_대조군_0은_거부한다():
    """D-032. 대조군 없이는 분모가 없어 에이전트가 생존 편향 규칙을 만든다."""
    with pytest.raises(SelectionError) as exc:
        select_candidates(
            _candidates(20), "2026-09-21", top_n=3, control_n=0, cohort=COHORT
        )
    assert "D-032" in str(exc.value)


def test_코호트가_비면_거부한다():
    """D-033. 기준선 없이는 오늘이 특이한지 판단할 수 없다."""
    with pytest.raises(SelectionError) as exc:
        select_candidates(
            _candidates(20), "2026-09-21", top_n=3, control_n=3, cohort=()
        )
    assert "D-033" in str(exc.value)


def test_상위군_0도_거부한다():
    with pytest.raises(SelectionError):
        select_candidates(
            _candidates(20), "2026-09-21", top_n=0, control_n=3, cohort=COHORT
        )


def test_중복_종목_입력을_거부한다():
    duplicated = _candidates(10) + [_candidates(10)[0]]
    with pytest.raises(SelectionError) as exc:
        select_candidates(
            duplicated, "2026-09-21", top_n=2, control_n=2, cohort=COHORT
        )
    assert "중복" in str(exc.value)


def test_전체_목록에_중복이_없다():
    """상위군·대조군·코호트가 겹칠 수 있으므로 합칠 때 중복이 제거되어야 한다."""
    selection = select_candidates(
        _candidates(40), "2026-09-21", top_n=5, control_n=5, cohort=COHORT
    )
    assert len(selection.all_codes) == len(set(selection.all_codes))


def test_동점이어도_순서가_흔들리지_않는다():
    """정렬이 불안정하면 재현이 깨진다."""
    tied = [
        Candidate(code=f"{i:06d}", name=f"종목{i}", change_pct=5.0, trading_value=5.0)
        for i in range(20)
    ]
    first = select_candidates(
        tied, "2026-09-21", top_n=3, control_n=3, cohort=COHORT
    )
    second = select_candidates(
        list(reversed(tied)), "2026-09-21", top_n=3, control_n=3, cohort=COHORT
    )
    assert first == second


def test_코호트_추첨은_같은_씨앗이면_같다():
    first = draw_cohort(_candidates(100), size=10, seed="cohort-2026")
    second = draw_cohort(_candidates(100), size=10, seed="cohort-2026")
    assert first == second
    assert len(first) == 10


def test_코호트_추첨은_씨앗이_다르면_달라진다():
    first = draw_cohort(_candidates(100), size=10, seed="cohort-2026")
    second = draw_cohort(_candidates(100), size=10, seed="cohort-2027")
    assert first != second


def test_코호트_추첨_크기가_0이면_거부한다():
    with pytest.raises(SelectionError):
        draw_cohort(_candidates(100), size=0, seed="cohort-2026")


def test_후보가_비면_코호트를_못_뽑는다():
    with pytest.raises(SelectionError):
        draw_cohort([], size=10, seed="cohort-2026")

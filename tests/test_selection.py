# 대조군이 실제로 생존 편향을 막는지, 그리고 선정이 재현 가능한지 검증한다 (D-032)

import pytest

from collector.selection import Candidate, SelectionError, select_candidates


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


def test_상위군은_등락률과_거래대금_각각_뽑는다():
    selection = select_candidates(_candidates(20), "2026-09-21", top_n=3, control_n=3)
    # 등락률은 index가 클수록 높다
    assert selection.top_by_change == ("000019", "000018", "000017")
    # 거래대금은 index가 작을수록 크다
    assert selection.top_by_value == ("000000", "000001", "000002")


def test_대조군은_상위군과_겹치지_않는다():
    selection = select_candidates(_candidates(30), "2026-09-21", top_n=5, control_n=5)
    상위군 = set(selection.top_by_change) | set(selection.top_by_value)
    assert not (set(selection.control) & 상위군)


def test_같은_날짜면_대조군까지_완전히_같다():
    """재현 불가능한 표본은 검증에 쓸 수 없다."""
    first = select_candidates(_candidates(50), "2026-09-21", top_n=3, control_n=7)
    second = select_candidates(_candidates(50), "2026-09-21", top_n=3, control_n=7)
    assert first == second


def test_날짜가_다르면_대조군이_달라진다():
    first = select_candidates(_candidates(50), "2026-09-21", top_n=3, control_n=7)
    second = select_candidates(_candidates(50), "2026-09-22", top_n=3, control_n=7)
    assert first.control != second.control


def test_대조군_0은_거부한다():
    """D-032. 대조군 없이는 분모가 없어 에이전트가 생존 편향 규칙을 만든다."""
    with pytest.raises(SelectionError) as exc:
        select_candidates(_candidates(20), "2026-09-21", top_n=3, control_n=0)
    assert "D-032" in str(exc.value)


def test_상위군_0도_거부한다():
    with pytest.raises(SelectionError):
        select_candidates(_candidates(20), "2026-09-21", top_n=0, control_n=3)


def test_중복_종목_입력을_거부한다():
    duplicated = _candidates(5) + [_candidates(5)[0]]
    with pytest.raises(SelectionError) as exc:
        select_candidates(duplicated, "2026-09-21", top_n=2, control_n=2)
    assert "중복" in str(exc.value)


def test_후보가_모자라도_있는_만큼만_뽑는다():
    selection = select_candidates(_candidates(6), "2026-09-21", top_n=2, control_n=10)
    상위군 = set(selection.top_by_change) | set(selection.top_by_value)
    assert set(selection.control) == set(f"{i:06d}" for i in range(6)) - 상위군


def test_전체_목록에_중복이_없다():
    """등락률 상위와 거래대금 상위가 겹칠 수 있으므로 합칠 때 중복이 제거되어야 한다."""
    candidates = [
        Candidate(code="000001", name="가", change_pct=9.0, trading_value=900.0),
        Candidate(code="000002", name="나", change_pct=8.0, trading_value=800.0),
        Candidate(code="000003", name="다", change_pct=1.0, trading_value=100.0),
        Candidate(code="000004", name="라", change_pct=0.5, trading_value=50.0),
    ]
    selection = select_candidates(candidates, "2026-09-21", top_n=2, control_n=1)
    assert selection.top_by_change == selection.top_by_value  # 같은 종목이 겹친다
    assert len(selection.all_codes) == len(set(selection.all_codes))


def test_동점이어도_순서가_흔들리지_않는다():
    """정렬이 불안정하면 재현이 깨진다."""
    tied = [
        Candidate(code=f"{i:06d}", name=f"종목{i}", change_pct=5.0, trading_value=5.0)
        for i in range(10)
    ]
    first = select_candidates(tied, "2026-09-21", top_n=3, control_n=3)
    second = select_candidates(list(reversed(tied)), "2026-09-21", top_n=3, control_n=3)
    assert first == second

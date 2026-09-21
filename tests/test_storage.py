# 무인 실행에서 중복 수집과 조용한 누락이 발생하지 않는지 검증한다

import json

import pytest

from collector.storage import DailyStore


def _store(tmp_path) -> DailyStore:
    return DailyStore(root=tmp_path, trade_date="2026-09-21")


def test_날짜별_폴더에_저장한다(tmp_path):
    store = _store(tmp_path)
    store.write_csv("daily_summary.csv", ["code", "close"], [["005930", 71200]])
    assert (tmp_path / "2026-09-21" / "daily_summary.csv").exists()


def test_이미_받은_자료는_다시_받지_않는다(tmp_path):
    store = _store(tmp_path)
    assert not store.has("daily_summary.csv")
    store.write_csv("daily_summary.csv", ["code"], [["005930"]])
    assert store.has("daily_summary.csv")


def test_하위_폴더도_만들어진다(tmp_path):
    store = _store(tmp_path)
    store.write_csv("minute/005930.csv", ["time", "close"], [["0901", 71200]])
    assert (tmp_path / "2026-09-21" / "minute" / "005930.csv").exists()


def test_실패가_로그에_남는다(tmp_path):
    store = _store(tmp_path)
    store.record_failure("minute/005930", "HTTP 500")
    log = json.loads(store.save_log().read_text(encoding="utf-8"))
    assert log["ok"] is False
    assert log["failed"] == [{"stage": "minute/005930", "reason": "HTTP 500"}]


def test_실패가_없으면_ok다(tmp_path):
    store = _store(tmp_path)
    store.write_csv("daily_summary.csv", ["code"], [["005930"]])
    log = json.loads(store.save_log().read_text(encoding="utf-8"))
    assert log["ok"] is True
    assert "daily_summary.csv" in log["completed"]


def test_일부만_실패해도_성공으로_보이지_않는다(tmp_path):
    """부분 성공을 성공으로 처리하면 구멍 난 데이터로 분석하게 된다."""
    store = _store(tmp_path)
    store.write_csv("daily_summary.csv", ["code"], [["005930"]])
    store.record_failure("minute/000660", "타임아웃")
    log = json.loads(store.save_log().read_text(encoding="utf-8"))
    assert log["ok"] is False


def test_건너뛴_항목도_기록된다(tmp_path):
    store = _store(tmp_path)
    store.record_skip("minute/005930.csv")
    log = json.loads(store.save_log().read_text(encoding="utf-8"))
    assert log["skipped"] == ["minute/005930.csv"]


def test_쓰다가_죽으면_파일이_남지_않는다(tmp_path):
    """반쯤 쓰인 파일이 남으면 다음 실행이 '이미 수집함'으로 오인한다."""
    store = _store(tmp_path)

    def 터지는_행():
        raise RuntimeError("수집 중 중단")

    class 터지는_목록(list):
        def __iter__(self):
            터지는_행()

    with pytest.raises(RuntimeError):
        store.write_csv("minute/005930.csv", ["time"], 터지는_목록())

    assert not store.has("minute/005930.csv")
    # 임시 파일도 남지 않아야 한다
    남은_파일 = list((tmp_path / "2026-09-21" / "minute").glob("*"))
    assert 남은_파일 == []


def test_한글이_깨지지_않는다(tmp_path):
    store = _store(tmp_path)
    store.write_json("selection.json", {"종목명": "삼성전자"})
    text = store.path_for("selection.json").read_text(encoding="utf-8")
    assert "삼성전자" in text

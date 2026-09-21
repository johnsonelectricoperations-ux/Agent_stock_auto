# 수집 결과를 날짜별로 저장한다. 무인 실행이므로 중복 수집과 조용한 누락을 막는 것이 목적이다

import csv
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


def _write_atomic(path: Path, write) -> None:
    """임시 파일에 다 쓴 뒤 이름을 바꾼다.

    중간에 프로세스가 죽으면 반쯤 쓰인 파일이 남고, 다음 실행이 그걸
    '이미 수집함'으로 오인해 영원히 구멍이 남는다. 이름 바꾸기는 원자적이라
    파일이 존재하면 항상 완전한 상태다.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as file:
            write(file)
        temp_path.replace(path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


@dataclass
class DailyStore:
    """하루치 수집 결과를 담는 폴더. 실패도 함께 기록한다."""

    root: Path
    trade_date: str
    completed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[dict[str, str]] = field(default_factory=list)

    @property
    def directory(self) -> Path:
        return Path(self.root) / self.trade_date

    def path_for(self, name: str) -> Path:
        return self.directory / name

    def has(self, name: str) -> bool:
        """이미 받아둔 자료인지 확인한다. 재실행 시 API를 다시 부르지 않기 위함이다."""
        return self.path_for(name).exists()

    def write_csv(self, name: str, header: Sequence[str], rows: list[Sequence]) -> None:
        def write(file):
            writer = csv.writer(file)
            writer.writerow(header)
            writer.writerows(rows)

        _write_atomic(self.path_for(name), write)
        self.completed.append(name)

    def write_json(self, name: str, payload: Any) -> None:
        def write(file):
            json.dump(payload, file, ensure_ascii=False, indent=2)

        _write_atomic(self.path_for(name), write)
        self.completed.append(name)

    def record_skip(self, name: str) -> None:
        self.skipped.append(name)

    def record_failure(self, stage: str, reason: str) -> None:
        """실패를 반드시 남긴다. 조용히 빠진 자료는 나중에 분석을 망친다."""
        self.failed.append({"stage": stage, "reason": reason})

    def save_log(self) -> Path:
        """이번 실행의 결과를 기록한다. 실패가 있으면 성공으로 보이지 않게 한다."""
        payload = {
            "trade_date": self.trade_date,
            "ok": not self.failed,
            "completed": sorted(self.completed),
            "skipped": sorted(self.skipped),
            "failed": self.failed,
        }
        path = self.path_for("collect_log.json")

        def write(file):
            json.dump(payload, file, ensure_ascii=False, indent=2)

        _write_atomic(path, write)
        return path

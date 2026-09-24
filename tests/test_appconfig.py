# 미정 값이 조용히 운용에 들어가지 않는지 검증한다 (핵심원칙 4)

import tomllib
from pathlib import Path

import pytest

from appconfig import PLACEHOLDER, Config, ConfigError, _flatten, load_config

SAMPLE = """
[time]
entry_cutoff = "14:30"
force_close = "15:20"

[risk]
max_positions = 3
max_loss_per_day = "<USER_DEFINED>"
"""


def _write(tmp_path, text=SAMPLE):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_확정된_키만_요구하면_통과한다(tmp_path):
    config = load_config(_write(tmp_path), required=["time.entry_cutoff", "risk.max_positions"])
    assert config.get("time.entry_cutoff") == "14:30"
    assert config.get("risk.max_positions") == 3


def test_미정_값을_요구하면_기동을_거부한다(tmp_path):
    with pytest.raises(ConfigError) as exc:
        load_config(_write(tmp_path), required=["risk.max_loss_per_day"])
    assert "risk.max_loss_per_day" in str(exc.value)
    assert "미정" in str(exc.value)


def test_없는_키를_요구하면_거부한다(tmp_path):
    with pytest.raises(ConfigError) as exc:
        load_config(_write(tmp_path), required=["risk.없는키"])
    assert "없는 키" in str(exc.value)


def test_미정과_누락을_한꺼번에_보고한다(tmp_path):
    """한 번에 다 알려줘야 고치러 여러 번 왕복하지 않는다."""
    with pytest.raises(ConfigError) as exc:
        load_config(
            _write(tmp_path),
            required=["risk.max_loss_per_day", "cost.없는키"],
        )
    message = str(exc.value)
    assert "risk.max_loss_per_day" in message
    assert "cost.없는키" in message


def test_프로세스마다_필요한_키가_다르다(tmp_path):
    """Collector는 리스크 한도가 필요 없다. 전부 검사하면 아무것도 시작 못 한다."""
    path = _write(tmp_path)
    load_config(path, required=["time.entry_cutoff"])  # 수집만 하는 경로 — 통과
    with pytest.raises(ConfigError):
        load_config(path, required=["risk.max_loss_per_day"])  # 주문 경로 — 거부


def test_설정_파일이_없으면_거부한다(tmp_path):
    with pytest.raises(ConfigError) as exc:
        load_config(tmp_path / "없는파일.toml", required=[])
    assert "설정 파일이 없다" in str(exc.value)


def test_get도_플레이스홀더를_거부한다():
    """required에서 빠뜨렸더라도 꺼내 쓰는 순간 막는다 (이중 방어)."""
    config = Config(values={"risk.max_loss_per_day": PLACEHOLDER})
    with pytest.raises(ConfigError):
        config.get("risk.max_loss_per_day")


def test_실제_설정파일은_전부_미정_상태다():
    """아직 아무 값도 확정되지 않았음을 고정한다.

    값을 채우기 시작하면 이 테스트가 깨진다. 그때 근거를 D-번호로 남기고 수정한다.
    """
    with Path("config.toml").open("rb") as file:
        flat = _flatten(tomllib.load(file))

    assert flat, "설정 파일이 비어 있다"
    정해진_값 = {key: value for key, value in flat.items() if value != PLACEHOLDER}
    assert not 정해진_값, f"근거 없이 채워진 값이 있다: {정해진_값}"


def test_설정파일에_비밀값이_없다():
    """API 키와 봇 토큰은 환경변수로만 주입한다. 설정 파일은 커밋되므로 들어가면 안 된다."""
    text = Path("config.toml").read_text(encoding="utf-8")
    금지어 = ["app_key", "app_secret", "bot_token", "api_key", "secret ="]
    발견 = [word for word in 금지어 if word in text.lower()]
    assert not 발견, f"설정 파일에 비밀값 키가 있다: {발견}"

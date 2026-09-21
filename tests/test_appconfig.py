# 미정 값이 조용히 운용에 들어가지 않는지 검증한다 (D-009)

import pytest

from appconfig import PLACEHOLDER, Config, ConfigError, load_config

SAMPLE = """
[observe]
top_n = 5
control_n = 5
min_days = "MUST_DEFINE"

[risk]
stop_loss_pct = "MUST_DEFINE"
"""


def _write(tmp_path, text=SAMPLE):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_확정된_키만_요구하면_통과한다(tmp_path):
    config = load_config(_write(tmp_path), required=["observe.top_n", "observe.control_n"])
    assert config.get("observe.top_n") == 5
    assert config.get("observe.control_n") == 5


def test_미정_값을_요구하면_기동을_거부한다(tmp_path):
    with pytest.raises(ConfigError) as exc:
        load_config(_write(tmp_path), required=["risk.stop_loss_pct"])
    assert "risk.stop_loss_pct" in str(exc.value)
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
            required=["risk.stop_loss_pct", "observe.min_days", "cost.없는키"],
        )
    message = str(exc.value)
    assert "risk.stop_loss_pct" in message
    assert "observe.min_days" in message
    assert "cost.없는키" in message


def test_모드마다_필요한_키가_다르다(tmp_path):
    """관찰 모드는 손절폭이 미정이어도 돌아야 한다. 전부 검사하면 시작조차 못 한다."""
    path = _write(tmp_path)
    load_config(path, required=["observe.top_n"])  # 관찰 모드 — 통과
    with pytest.raises(ConfigError):
        load_config(path, required=["risk.stop_loss_pct"])  # 실매매 모드 — 거부


def test_설정_파일이_없으면_거부한다(tmp_path):
    with pytest.raises(ConfigError) as exc:
        load_config(tmp_path / "없는파일.toml", required=[])
    assert "설정 파일이 없다" in str(exc.value)


def test_get도_플레이스홀더를_거부한다():
    """required에서 빠뜨렸더라도 꺼내 쓰는 순간 막는다 (이중 방어)."""
    config = Config(values={"risk.stop_loss_pct": PLACEHOLDER})
    with pytest.raises(ConfigError):
        config.get("risk.stop_loss_pct")


def test_실제_설정파일은_전부_미정_상태다():
    """아직 아무 값도 확정되지 않았음을 고정한다.

    값을 채우기 시작하면 이 테스트가 깨진다. 그때 근거를 D-번호로 남기고 수정한다.
    """
    from appconfig import _flatten
    import tomllib
    from pathlib import Path

    with Path("config.toml").open("rb") as file:
        flat = _flatten(tomllib.load(file))

    assert flat, "설정 파일이 비어 있다"
    정해진_값 = {key: value for key, value in flat.items() if value != PLACEHOLDER}
    assert not 정해진_값, f"근거 없이 채워진 값이 있다: {정해진_값}"

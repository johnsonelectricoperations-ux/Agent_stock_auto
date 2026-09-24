# 설정 파일을 읽고 미정 플레이스홀더가 남아 있으면 기동을 거부한다 (D-009)

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# 아직 정해지지 않은 값을 나타내는 표식. 이 값이 실제 운용에 들어가면 안 된다 (핵심원칙 4).
PLACEHOLDER = "<USER_DEFINED>"

DEFAULT_CONFIG_PATH = Path("config.toml")


class ConfigError(Exception):
    """설정이 운용에 쓸 수 없는 상태일 때 올린다."""


def _flatten(data: dict, prefix: str = "") -> dict[str, Any]:
    """중첩된 표를 'cost.commission_buy' 같은 점 표기 키로 펼친다."""
    flat: dict[str, Any] = {}
    for key, value in data.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{path}."))
        else:
            flat[path] = value
    return flat


@dataclass(frozen=True)
class Config:
    values: dict[str, Any]

    def get(self, key: str) -> Any:
        """값을 꺼낸다. 플레이스홀더면 여기서도 거부한다 (이중 방어)."""
        if key not in self.values:
            raise ConfigError(f"설정에 없는 키다: {key}")
        value = self.values[key]
        if value == PLACEHOLDER:
            raise ConfigError(f"아직 정해지지 않은 값이다: {key}")
        return value


def load_config(path: Path | str, required: list[str]) -> Config:
    """설정을 읽고, 이번 실행에 필요한 키가 전부 확정되어 있는지 기동 시점에 검사한다.

    필요한 키만 검사하는 이유는 모드마다 쓰는 값이 다르기 때문이다.
    관찰 모드는 손절폭이 필요 없고, 실매매 모드는 필요하다.
    전부를 검사하면 관찰조차 시작할 수 없다.

    실행 도중이 아니라 시작할 때 실패시킨다. 주문을 낸 뒤에 멈추면 늦는다.
    """
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"설정 파일이 없다: {path}")

    with path.open("rb") as file:
        raw = tomllib.load(file)

    flat = _flatten(raw)

    missing = [key for key in required if key not in flat]
    undefined = [key for key in required if flat.get(key) == PLACEHOLDER]

    if missing or undefined:
        lines = [f"설정이 준비되지 않았다 ({path})"]
        if missing:
            lines.append(f"  없는 키: {', '.join(sorted(missing))}")
        if undefined:
            lines.append(f"  미정 값: {', '.join(sorted(undefined))}")
            lines.append(f"  → {path}에서 {PLACEHOLDER}를 실제 값으로 바꾼다")
        raise ConfigError("\n".join(lines))

    return Config(values=flat)

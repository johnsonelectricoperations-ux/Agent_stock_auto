# 네트워크 없이 검증 가능한 부분만 테스트한다. 실제 접속 확인은 Actions에서 수행한다 (D-020)

import pytest

from collector.kis_client import (
    PROD_BASE_URL,
    VTS_BASE_URL,
    KisCredentials,
    KisError,
)


def test_환경변수가_비면_기본값_없이_중단한다(monkeypatch):
    """D-009. 임의 기본값을 만들지 않고 명시적으로 실패시킨다."""
    monkeypatch.delenv("KIS_APP_KEY", raising=False)
    monkeypatch.delenv("KIS_APP_SECRET", raising=False)
    with pytest.raises(KisError) as exc:
        KisCredentials.from_env()
    assert "KIS_APP_KEY" in str(exc.value)
    assert "KIS_APP_SECRET" in str(exc.value)


def test_한쪽만_있어도_중단한다(monkeypatch):
    monkeypatch.setenv("KIS_APP_KEY", "키")
    monkeypatch.delenv("KIS_APP_SECRET", raising=False)
    with pytest.raises(KisError) as exc:
        KisCredentials.from_env()
    assert "KIS_APP_SECRET" in str(exc.value)


def test_공백만_있는_값은_비어있는_것으로_본다(monkeypatch):
    monkeypatch.setenv("KIS_APP_KEY", "   ")
    monkeypatch.setenv("KIS_APP_SECRET", "시크릿")
    with pytest.raises(KisError):
        KisCredentials.from_env()


def test_기본은_실전_서버다(monkeypatch):
    monkeypatch.setenv("KIS_APP_KEY", "키")
    monkeypatch.setenv("KIS_APP_SECRET", "시크릿")
    monkeypatch.delenv("KIS_USE_VTS", raising=False)
    assert KisCredentials.from_env().base_url == PROD_BASE_URL


def test_모의투자_전환이_동작한다(monkeypatch):
    monkeypatch.setenv("KIS_APP_KEY", "키")
    monkeypatch.setenv("KIS_APP_SECRET", "시크릿")
    monkeypatch.setenv("KIS_USE_VTS", "true")
    assert KisCredentials.from_env().base_url == VTS_BASE_URL


def test_자격증명이_로그로_새지_않는다(monkeypatch):
    """예외 메시지에 키나 시크릿이 들어가면 CI 로그에 남는다 (D-020 보안)."""
    monkeypatch.setenv("KIS_APP_KEY", "비밀키값")
    monkeypatch.delenv("KIS_APP_SECRET", raising=False)
    with pytest.raises(KisError) as exc:
        KisCredentials.from_env()
    assert "비밀키값" not in str(exc.value)

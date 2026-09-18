# KIS Open API 인증과 최소 조회를 담당하는 클라이언트. 접속 가능 여부 검증용 최소 구현이다 (D-019, D-020)

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

PROD_BASE_URL = "https://openapi.koreainvestment.com:9443"
VTS_BASE_URL = "https://openapivts.koreainvestment.com:29443"

# 국내주식 현재가 시세 조회
TR_ID_INQUIRE_PRICE = "FHKST01010100"

# 코스피/코스닥 통합 시장 구분 코드
MARKET_DIV_CODE = "J"

REQUEST_TIMEOUT_SEC = 20


class KisError(Exception):
    """KIS API 호출이 실패했을 때 올린다. 메시지에 키나 토큰을 넣지 않는다."""


@dataclass(frozen=True)
class KisCredentials:
    app_key: str
    app_secret: str
    use_vts: bool

    @property
    def base_url(self) -> str:
        return VTS_BASE_URL if self.use_vts else PROD_BASE_URL

    @classmethod
    def from_env(cls) -> "KisCredentials":
        """환경변수에서 읽는다. 값이 없으면 기본값을 만들지 않고 중단한다 (D-009)."""
        app_key = os.environ.get("KIS_APP_KEY", "").strip()
        app_secret = os.environ.get("KIS_APP_SECRET", "").strip()
        missing = [
            name
            for name, value in (
                ("KIS_APP_KEY", app_key),
                ("KIS_APP_SECRET", app_secret),
            )
            if not value
        ]
        if missing:
            raise KisError(f"환경변수가 비어 있다: {', '.join(missing)}")
        return cls(
            app_key=app_key,
            app_secret=app_secret,
            use_vts=os.environ.get("KIS_USE_VTS", "").lower() in ("1", "true", "yes"),
        )


def _request(url: str, *, method: str, headers: dict, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SEC) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise KisError(f"HTTP {exc.code} — {detail}") from exc
    except urllib.error.URLError as exc:
        raise KisError(f"접속 실패 — {exc.reason}") from exc


def issue_access_token(credentials: KisCredentials) -> str:
    """접근토큰을 발급받는다. 발급 호출 자체에 빈도 제한이 있으므로 남발하지 않는다."""
    payload = _request(
        f"{credentials.base_url}/oauth2/tokenP",
        method="POST",
        headers={"content-type": "application/json; charset=utf-8"},
        body={
            "grant_type": "client_credentials",
            "appkey": credentials.app_key,
            "appsecret": credentials.app_secret,
        },
    )
    token = payload.get("access_token")
    if not token:
        raise KisError(f"응답에 access_token이 없다 — 키: {sorted(payload)}")
    return token


def fetch_current_price(
    credentials: KisCredentials, access_token: str, stock_code: str
) -> dict:
    """종목 현재가를 조회한다. 접속 가능 여부 확인이 목적이라 원본 output을 그대로 돌려준다."""
    query = urllib.parse.urlencode(
        {"FID_COND_MRKT_DIV_CODE": MARKET_DIV_CODE, "FID_INPUT_ISCD": stock_code}
    )
    payload = _request(
        f"{credentials.base_url}/uapi/domestic-stock/v1/quotations/inquire-price?{query}",
        method="GET",
        headers={
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {access_token}",
            "appkey": credentials.app_key,
            "appsecret": credentials.app_secret,
            "tr_id": TR_ID_INQUIRE_PRICE,
        },
    )
    # rt_cd가 "0"이 아니면 실패다. 조용히 넘기지 않는다.
    if payload.get("rt_cd") != "0":
        raise KisError(
            f"조회 실패 rt_cd={payload.get('rt_cd')} msg={payload.get('msg1')}"
        )
    output = payload.get("output")
    if not output:
        raise KisError("응답에 output이 비어 있다")
    return output

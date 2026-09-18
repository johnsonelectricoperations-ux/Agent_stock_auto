# GitHub Actions 해외 IP에서 KIS API에 접속되는지 확인한다. D-020의 선결 과제다.

import sys

from collector.kis_client import (
    KisCredentials,
    KisError,
    fetch_current_price,
    issue_access_token,
)

# 접속 확인용 종목. 삼성전자는 상장폐지·거래정지 가능성이 사실상 없어 고정 대조군으로 쓴다.
CHECK_STOCK_CODE = "005930"


def main() -> int:
    try:
        credentials = KisCredentials.from_env()
    except KisError as exc:
        print(f"[실패] 자격증명 로딩 — {exc}")
        print("GitHub Secrets에 KIS_APP_KEY와 KIS_APP_SECRET을 등록했는지 확인한다.")
        return 1

    print(f"대상 서버: {credentials.base_url}")

    try:
        access_token = issue_access_token(credentials)
    except KisError as exc:
        print(f"[실패] 토큰 발급 — {exc}")
        print("해외 IP 차단이라면 여기서 막힌다. 집 PC나 한국 리전 VPS로 전환을 검토한다.")
        return 1
    print("[통과] 토큰 발급")

    try:
        output = fetch_current_price(credentials, access_token, CHECK_STOCK_CODE)
    except KisError as exc:
        print(f"[실패] 시세 조회 — {exc}")
        return 1

    print("[통과] 시세 조회")
    print(f"  종목명   {output.get('rprs_mrkt_kor_name', '?')} / {CHECK_STOCK_CODE}")
    print(f"  현재가   {output.get('stck_prpr', '?')}")
    print(f"  등락률   {output.get('prdy_ctrt', '?')}%")
    print()
    print("결론: GitHub Actions에서 KIS API 사용이 가능하다. O1 수집기로 진행한다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

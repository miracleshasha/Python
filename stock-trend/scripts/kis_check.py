"""KIS Open API 연결 진단 스크립트.

실제 앱키/시크릿으로 각 기능(토큰·현재가·분봉·수급)을 개별 점검한다.
실패하거나 결과가 비면 **원본 JSON 응답**을 출력해 필드/‌tr_id 불일치를 바로 확인할 수 있다.

사용:
    export KIS_APP_KEY=...  KIS_APP_SECRET=...   # (모의면 export KIS_ENV=vps)
    python scripts/kis_check.py                  # 기본 005930(삼성전자)
    python scripts/kis_check.py 000660           # 특정 종목
"""
from __future__ import annotations

import json
import os
import sys

# 프로젝트 루트를 import 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.providers import kis  # noqa: E402


def _hr(title):
    print("\n" + "=" * 60 + f"\n{title}\n" + "-" * 60)


def _raw(path, tr_id, params):
    """원본 JSON을 그대로 출력(필드명 확인용)."""
    data = kis._get(path, tr_id, params)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:2000] or "(빈 응답)")


def main(ticker: str) -> int:
    _hr("0) 환경 점검")
    print("KIS_APP_KEY 설정:", bool(os.environ.get("KIS_APP_KEY")))
    print("KIS_APP_SECRET 설정:", bool(os.environ.get("KIS_APP_SECRET")))
    print("KIS_ENV:", os.environ.get("KIS_ENV", "real"), "| base:", kis._base())
    print("available():", kis.available())
    if not kis.available():
        print("\n⚠️ 키가 없거나 requests 미설치입니다. 환경변수를 설정하고 다시 실행하세요.")
        return 1

    _hr("1) 액세스 토큰 발급")
    token = kis._access_token()
    print("토큰 발급:", "성공" if token else "실패")
    if not token:
        print("→ tokenP 응답 확인이 필요합니다. 앱키/시크릿·실전/모의(KIS_ENV) 여부를 점검하세요.")
        return 1

    _hr(f"2) 현재가 inquire-price ({ticker})")
    price = kis.current_price(ticker)
    print("파싱 결과:", price or "(빈 결과)")
    if not price:
        print("\n[원본 응답]")
        _raw("/uapi/domestic-stock/v1/quotations/inquire-price", "FHKST01010100",
             {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ticker[:6]})

    _hr(f"3) 당일 분봉 inquire-time-itemchartprice ({ticker})")
    mdf = kis.minute_candles(ticker)
    print("분봉 행 수:", len(mdf))
    if not mdf.empty:
        print(mdf.tail(3))
    else:
        print("\n[원본 응답]")
        import datetime
        _raw("/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice", "FHKST03010200",
             {"FID_ETC_CLS_CODE": "", "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ticker[:6],
              "FID_INPUT_HOUR_1": datetime.datetime.now().strftime("%H%M%S"),
              "FID_PW_DATA_INCU_YN": "Y"})

    _hr("4) 수급 foreign-institution-total (KOSPI)")
    fdf = kis.foreign_institution_total("KOSPI")
    print("종목 수:", len(fdf))
    if not fdf.empty:
        print(fdf.head(5))
    else:
        print("\n[원본 응답]")
        _raw("/uapi/domestic-stock/v1/quotations/foreign-institution-total", "FHPTJ04400000",
             {"FID_COND_MRKT_DIV_CODE": "V", "FID_COND_SCR_DIV_CODE": "16449",
              "FID_INPUT_ISCD": "0001", "FID_DIV_CLS_CODE": "1",
              "FID_RANK_SORT_CLS_CODE": "0", "FID_ETC_CLS_CODE": "0"})

    _hr("완료")
    print("각 항목이 '성공/결과 있음'이면 앱에서도 동작합니다.")
    print("빈 결과·원본 응답이 보이면 그 JSON을 공유해 주세요 — 필드명/tr_id를 맞추겠습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "005930"))

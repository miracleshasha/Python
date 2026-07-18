"""시장 구분 및 티커 정규화.

국내(KRX)/미국(US) 시장을 티커 형태로 판별한다. 미국 확장 시 이 모듈이
시장 판별의 단일 기준점이 된다(향후 US 종목 규칙·거래소 매핑 추가 지점).
"""
from __future__ import annotations

import re
from enum import Enum


class Market(str, Enum):
    KR = "KR"   # 한국 (KRX: KOSPI/KOSDAQ)
    US = "US"   # 미국 (NYSE/NASDAQ)


# 한국 티커: 6자리 숫자(+선택적 .KS/.KQ). 예) 005930, 005930.KS
_KR_TICKER_RE = re.compile(r"^\d{6}(\.(KS|KQ))?$", re.IGNORECASE)


def detect_market(ticker: str) -> Market:
    """티커로 시장을 판별한다."""
    return Market.KR if _KR_TICKER_RE.match(ticker.strip().upper()) else Market.US


def normalize_ticker(raw: str) -> tuple[str, bool]:
    """사용자 입력을 조회용 티커로 정규화한다.

    반환: (조회용 티커, 한국 종목 여부)
    - '005930'   -> ('005930.KS', True)   # 접미사 없으면 코스피로 가정
    - '005930.KQ'-> ('005930.KQ', True)
    - 'AAPL'     -> ('AAPL', False)
    """
    t = raw.strip().upper()
    if _KR_TICKER_RE.match(t):
        if "." not in t:
            t = f"{t}.KS"
        return t, True
    return t, False

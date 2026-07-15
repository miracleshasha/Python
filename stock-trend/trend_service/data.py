"""시세 데이터 조회 계층.

yfinance로 종목 OHLCV와 시장심리 지수(VIX, SOX)를 가져온다.
한국 종목은 티커 접미사(.KS/.KQ)로, 미국 종목은 심볼 그대로 조회한다.
외국인 수급은 국내 종목에 한해 pykrx가 설치돼 있을 때만 선택적으로 조회한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Optional

import pandas as pd

try:  # yfinance는 필수 의존성이지만, import 실패 시 친절히 알려준다.
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

import config


# 한국 티커: 6자리 숫자(+선택적 .KS/.KQ). 예) 005930, 005930.KS
_KR_TICKER_RE = re.compile(r"^\d{6}(\.(KS|KQ))?$", re.IGNORECASE)


@dataclass
class StockData:
    """조회 결과 묶음."""
    ticker: str            # 정규화된 조회용 티커 (예: 005930.KS)
    raw_input: str         # 사용자가 입력한 원본
    is_korean: bool
    ohlcv: pd.DataFrame     # index=Date, columns=Open/High/Low/Close/Volume


def normalize_ticker(raw: str) -> tuple[str, bool]:
    """사용자 입력을 yfinance 조회용 티커로 정규화한다.

    반환: (조회용 티커, 한국 종목 여부)
    - '005930' -> ('005930.KS', True)   # 접미사 없으면 코스피로 가정
    - '005930.KQ' -> ('005930.KQ', True)
    - 'AAPL' -> ('AAPL', False)
    """
    t = raw.strip().upper()
    if _KR_TICKER_RE.match(t):
        if "." not in t:
            t = f"{t}.KS"
        return t, True
    return t, False


def _empty_ohlcv() -> pd.DataFrame:
    return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])


def fetch_ohlcv(ticker: str, period: str = config.DEFAULT_PERIOD) -> pd.DataFrame:
    """yfinance로 OHLCV를 가져온다. 실패하면 빈 DataFrame."""
    if yf is None:
        raise RuntimeError(
            "yfinance가 설치돼 있지 않습니다. `pip install -r requirements.txt`를 실행하세요."
        )
    try:
        df = yf.Ticker(ticker).history(period=period, auto_adjust=False)
    except Exception:
        # 네트워크 차단/조회 실패 등은 빈 결과로 처리해 UI가 우아하게 폴백하도록 한다.
        return _empty_ohlcv()
    if df is None or df.empty:
        return _empty_ohlcv()
    # 필요한 컬럼만, 결측 제거
    cols = ["Open", "High", "Low", "Close", "Volume"]
    df = df[[c for c in cols if c in df.columns]].dropna()
    return df


@lru_cache(maxsize=64)
def _fetch_cached(ticker: str, period: str, _bucket: int) -> pd.DataFrame:
    # _bucket은 시간 기반 캐시 무효화용 키(config.CACHE_TTL_SECONDS 마다 변경).
    return fetch_ohlcv(ticker, period)


def _time_bucket() -> int:
    return int(datetime.now().timestamp() // config.CACHE_TTL_SECONDS)


def get_stock_data(raw_ticker: str, period: str = config.DEFAULT_PERIOD) -> StockData:
    """종목 데이터 조회 진입점(캐시 포함)."""
    ticker, is_kr = normalize_ticker(raw_ticker)
    ohlcv = _fetch_cached(ticker, period, _time_bucket())
    return StockData(ticker=ticker, raw_input=raw_ticker, is_korean=is_kr, ohlcv=ohlcv.copy())


def get_market_index(symbol: str, period: str = config.DEFAULT_PERIOD) -> pd.DataFrame:
    """VIX/SOX 같은 시장 지수 OHLCV 조회. 실패 시 빈 DataFrame."""
    try:
        return _fetch_cached(symbol, period, _time_bucket()).copy()
    except Exception:
        return _empty_ohlcv()


def get_foreign_netbuy(ticker: str, days: int = 10) -> Optional[pd.Series]:
    """국내 종목 외국인 순매수(주식수) 최근 시계열. pykrx 없으면 None.

    반환 Series: index=날짜, value=외국인 순매수 수량(+매수/-매도).
    """
    code_match = re.match(r"^(\d{6})", ticker)
    if not code_match:
        return None
    try:
        from pykrx import stock as krx  # 선택적 의존성
    except ImportError:
        return None
    try:
        code = code_match.group(1)
        end = datetime.now()
        # 영업일 여유를 두고 넉넉히 조회
        start = end - pd.Timedelta(days=days * 3 + 10)
        df = krx.get_market_trading_value_by_date(
            start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), code
        )
        if df is None or df.empty or "외국인합계" not in df.columns:
            return None
        return df["외국인합계"].tail(days)
    except Exception:
        return None

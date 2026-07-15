"""시세 데이터 조회 계층.

국내 종목 시세는 **금융위원회 주식시세정보 API(data.go.kr)** 를 우선 사용하고
(환경변수 DATA_GO_KR_API_KEY 필요), 실패 시 yfinance로 폴백한다.
미국 종목과 시장심리 지수(VIX, SOX)는 yfinance로 조회한다.
외국인/기관/개인 수급은 금융위 API엔 없는 데이터라, 국내 종목에 한해 pykrx(KRX)로 조회한다.
(pykrx는 기본 의존성이나 국내 네트워크가 필요 — 실패 시 None 폴백)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Optional

import pandas as pd

try:  # yfinance는 미국 종목/지수용. import 실패 시 친절히 알려준다.
    import yfinance as yf
except ImportError:  # pragma: no cover
    yf = None

import config
from trend_service import krx_api


# 한국 티커: 6자리 숫자(+선택적 .KS/.KQ). 예) 005930, 005930.KS
_KR_TICKER_RE = re.compile(r"^\d{6}(\.(KS|KQ))?$", re.IGNORECASE)


@dataclass
class StockData:
    """조회 결과 묶음."""
    ticker: str            # 정규화된 조회용 티커 (예: 005930.KS)
    raw_input: str         # 사용자가 입력한 원본
    is_korean: bool
    ohlcv: pd.DataFrame     # index=Date, columns=Open/High/Low/Close/Volume
    name: Optional[str] = None  # 종목명(회사명). 조회 실패 시 None

    @property
    def display_name(self) -> str:
        """UI 표기용: '종목명 (티커)' 또는 이름 없으면 티커."""
        return f"{self.name} ({self.ticker})" if self.name else self.ticker


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
    """OHLCV 조회. 국내=금융위 API 우선(→yfinance 폴백), 미국=yfinance."""
    is_kr = bool(_KR_TICKER_RE.match(ticker.strip().upper()))

    # 1) 국내 종목: 금융위원회 주식시세정보 API 우선
    if is_kr and krx_api.api_key():
        df = krx_api.fetch_ohlcv(ticker, period)
        if not df.empty:
            return df
        # 키는 있으나 조회 실패 시 아래 yfinance로 폴백

    # 2) yfinance (미국 종목, 또는 국내 폴백)
    if yf is None:
        return _empty_ohlcv()
    try:
        df = yf.Ticker(ticker).history(period=period, auto_adjust=False)
    except Exception:
        # 네트워크 차단/조회 실패 등은 빈 결과로 처리해 UI가 우아하게 폴백하도록 한다.
        return _empty_ohlcv()
    if df is None or df.empty:
        return _empty_ohlcv()
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
    name = get_ticker_name(ticker, is_kr) if not ohlcv.empty else None
    return StockData(ticker=ticker, raw_input=raw_ticker, is_korean=is_kr,
                     ohlcv=ohlcv.copy(), name=name)


@lru_cache(maxsize=256)
def get_ticker_name(ticker: str, is_korean: bool) -> Optional[str]:
    """종목명(회사명)을 조회한다. 실패 시 None(폴백).

    - 국내: pykrx `get_market_ticker_name`(네트워크). 없으면 yfinance로 폴백.
    - 미국: yfinance `fast_info`/`info`의 이름 필드.
    """
    # 국내: 금융위 API → pykrx 순
    code_match = re.match(r"^(\d{6})", ticker)
    if is_korean and code_match:
        if krx_api.api_key():
            name = krx_api.fetch_name(ticker)
            if name:
                return str(name)
        try:
            from pykrx import stock as krx
            name = krx.get_market_ticker_name(code_match.group(1))
            if name:
                return str(name)
        except Exception:
            pass
    # yfinance 폴백 (미국 종목 또는 국내 pykrx 실패 시)
    if yf is not None:
        try:
            info = getattr(yf.Ticker(ticker), "info", None) or {}
            for key in ("longName", "shortName", "displayName"):
                if info.get(key):
                    return str(info[key])
        except Exception:
            pass
    return None


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


def get_investor_flows(ticker: str, days: int = 20) -> Optional[pd.DataFrame]:
    """국내 종목 투자자별 순매수(거래대금) 최근 시계열. pykrx 없으면 None.

    반환 DataFrame: index=날짜, columns=['외국인', '기관', '개인'] (순매수 금액, +매수/-매도).
    미국 종목/데이터 부재 시 None.
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
        start = end - pd.Timedelta(days=days * 3 + 15)
        df = krx.get_market_trading_value_by_date(
            start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), code
        )
        if df is None or df.empty:
            return None
        # pykrx 컬럼: 기관합계/외국인합계/개인/기타법인 등 (버전에 따라 상이)
        colmap = {}
        for src, dst in (("외국인합계", "외국인"), ("기관합계", "기관"), ("개인", "개인")):
            if src in df.columns:
                colmap[src] = dst
        if not colmap:
            return None
        out = df[list(colmap)].rename(columns=colmap).tail(days)
        return out
    except Exception:
        return None

"""KRX(국내) 데이터 provider — pykrx 기반.

지수 구성종목 · 펀더멘털/시총/종가 횡단면 · 종목명을 조회한다.
pykrx 미설치 또는 KRX 접근 차단(해외/클라우드) 시 빈 결과로 폴백한다.
모든 조회는 '특정일 전 종목 한 번에'(횡단면)라 호출 수가 적다.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd


def _krx():
    """pykrx.stock 모듈 반환(없으면 None)."""
    try:
        from pykrx import stock
        return stock
    except Exception:
        return None


def business_day(date: Optional[str] = None) -> str:
    """조회 기준 영업일(YYYYMMDD). date 없으면 최근 영업일."""
    stock = _krx()
    if date:
        return date
    if stock is not None:
        try:
            return stock.get_nearest_business_day_in_a_week()
        except Exception:
            pass
    return datetime.now().strftime("%Y%m%d")


def date_months_ago(months: int, ref: Optional[str] = None) -> str:
    base = datetime.strptime(ref, "%Y%m%d") if ref else datetime.now()
    approx = base - timedelta(days=int(months * 30.4))
    stock = _krx()
    if stock is not None:
        try:
            return stock.get_nearest_business_day_in_a_week(approx.strftime("%Y%m%d"))
        except Exception:
            pass
    return approx.strftime("%Y%m%d")


def index_constituents(index_code: str) -> list[str]:
    stock = _krx()
    if stock is None:
        return []
    try:
        tickers = stock.get_index_portfolio_deposit_file(index_code)
        return list(tickers) if tickers else []
    except Exception:
        try:  # 일부 버전은 (date, ticker) 시그니처
            return list(stock.get_index_portfolio_deposit_file(business_day(), index_code))
        except Exception:
            return []


def fundamental_snapshot(market: str, date: Optional[str] = None) -> pd.DataFrame:
    stock = _krx()
    if stock is None:
        return pd.DataFrame()
    try:
        df = stock.get_market_fundamental_by_ticker(business_day(date), market=market)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def marketcap_snapshot(market: str, date: Optional[str] = None) -> pd.DataFrame:
    stock = _krx()
    if stock is None:
        return pd.DataFrame()
    try:
        df = stock.get_market_cap_by_ticker(business_day(date), market=market)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def close_snapshot(market: str, date: Optional[str] = None) -> pd.Series:
    stock = _krx()
    if stock is None:
        return pd.Series(dtype=float)
    try:
        df = stock.get_market_ohlcv_by_ticker(business_day(date), market=market)
        if df is None or df.empty or "종가" not in df.columns:
            return pd.Series(dtype=float)
        return df["종가"].astype(float)
    except Exception:
        return pd.Series(dtype=float)


def ticker_name(ticker: str) -> Optional[str]:
    stock = _krx()
    if stock is None:
        return None
    try:
        name = stock.get_market_ticker_name(ticker[:6])
        return str(name) if name else None
    except Exception:
        return None

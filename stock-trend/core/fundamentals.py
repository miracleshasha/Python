"""펀더멘털 스냅샷 조립.

유니버스 종목의 밸류·퀄리티·모멘텀 원지표를 하나의 DataFrame으로 만든다.
시장별 횡단면 조회(펀더멘털/시총/종가)를 합쳐 종목별로 정리한다.
ROE는 pykrx가 직접 주지 않으므로 PBR/PER(≈EPS/BPS)로 근사한다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config
from core import cache
from core.providers import krx


def _snapshot_for_market(market: str) -> pd.DataFrame:
    """한 시장(KOSPI/KOSDAQ)의 펀더멘털+시총+모멘텀 횡단면."""
    day = krx.business_day()
    fund = krx.fundamental_snapshot(market)              # PER/PBR/EPS/BPS/DIV
    if fund is None or fund.empty:
        return pd.DataFrame()
    cap = krx.marketcap_snapshot(market)                 # 시가총액
    close_now = krx.close_snapshot(market)               # 종가(현재)
    close_past = krx.close_snapshot(market, krx.date_months_ago(config.QUANT_MOMENTUM_MONTHS))

    df = fund.copy()
    if cap is not None and not cap.empty and "시가총액" in cap.columns:
        df["MKTCAP"] = cap["시가총액"]
    # 모멘텀: 현재/과거 종가 비율 - 1
    if not close_now.empty and not close_past.empty:
        mom = (close_now / close_past.reindex(close_now.index)) - 1.0
        df["MOM"] = mom
    df["market"] = market
    return df


def get_snapshot(universe: pd.DataFrame) -> pd.DataFrame:
    """유니버스 종목의 통합 팩터 원지표 스냅샷.

    반환 DataFrame: index=ticker, cols=[PER,PBR,DIV,ROE,MKTCAP,MOM,market].
    실패/데이터 없음 시 빈 DF.
    """
    if universe is None or universe.empty:
        return pd.DataFrame()

    markets = sorted(universe["market"].unique())
    parts = []
    for m in markets:
        snap = cache.get_or_compute(
            f"fundamentals_{m}_{krx.business_day()}",
            lambda m=m: _snapshot_for_market(m),
        )
        if not snap.empty:
            parts.append(snap)
    if not parts:
        return pd.DataFrame()

    full = pd.concat(parts)
    # 유니버스 종목만
    tickers = [t for t in universe["ticker"] if t in full.index]
    df = full.loc[tickers].copy()

    # 표준 컬럼 정리 + ROE 근사(PBR/PER)
    out = pd.DataFrame(index=df.index)
    out["PER"] = pd.to_numeric(df.get("PER"), errors="coerce")
    out["PBR"] = pd.to_numeric(df.get("PBR"), errors="coerce")
    out["DIV"] = pd.to_numeric(df.get("DIV"), errors="coerce")
    out["MKTCAP"] = pd.to_numeric(df.get("MKTCAP"), errors="coerce")
    out["MOM"] = pd.to_numeric(df.get("MOM"), errors="coerce")
    roe = (out["PBR"] / out["PER"]).replace([np.inf, -np.inf], np.nan)  # ≈ EPS/BPS
    out["ROE"] = roe
    out["market"] = df.get("market")
    return out

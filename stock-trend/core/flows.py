"""투자자별 수급 스코어 (횡단면).

외국인·기관·개인의 기간 순매수(거래대금)를 종목별로 모아 수급 스코어를 만든다.
'스마트머니'(외국인+기관) 순매수를 매수세로 본다. pykrx 횡단면 조회라 호출이 적다.
"""
from __future__ import annotations

import pandas as pd

import config
from core import cache
from core.providers import kis
from core.providers import krx


def get_flows(market: str, days: int | None = None) -> pd.DataFrame:
    """시장 전체 투자자별 순매수(거래대금) 스냅샷.

    소스 우선순위(수급 클라우드 대응): KIS(전역) → pykrx(국내망).
    반환 DataFrame: index=티커, cols=[외국인, 기관(, 개인)]. 실패 시 빈 DF.
    """
    days = days or config.PREDICT_FLOW_DAYS
    end = krx.business_day()

    def _compute() -> pd.DataFrame:
        # 1) KIS: 기관·외국인 매매종목 가집계(횡단면, 클라우드 OK)
        if kis.available():
            df = kis.foreign_institution_total(market)
            if not df.empty:
                return df
        # 2) pykrx: 투자자별 순매수(국내망)
        start = krx.date_months_ago(max(1, days // 20))
        cols = {}
        for label, investor in (("외국인", "외국인"), ("기관", "기관합계"), ("개인", "개인")):
            s = krx.net_purchases(market, start, end, investor)
            if not s.empty:
                cols[label] = s
        return pd.DataFrame(cols) if cols else pd.DataFrame()

    return cache.get_or_compute(f"flows_{market}_{end}_{days}", _compute)


def smart_money(flows: pd.DataFrame) -> pd.Series:
    """스마트머니(외국인+기관) 순매수 합계. 수급 스코어의 원지표."""
    if flows is None or flows.empty:
        return pd.Series(dtype=float)
    cols = [c for c in ("외국인", "기관") if c in flows.columns]
    if not cols:
        return pd.Series(dtype=float)
    return flows[cols].sum(axis=1)

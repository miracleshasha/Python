"""투자자별 수급 스코어 (횡단면).

외국인·기관·개인의 기간 순매수(거래대금)를 종목별로 모아 수급 스코어를 만든다.
'스마트머니'(외국인+기관) 순매수를 매수세로 본다. pykrx 횡단면 조회라 호출이 적다.
"""
from __future__ import annotations

import pandas as pd

import config
from core import cache
from core.providers import krx


def get_flows(market: str, days: int | None = None) -> pd.DataFrame:
    """시장 전체 투자자별 순매수(거래대금) 스냅샷.

    반환 DataFrame: index=티커, cols=[외국인, 기관, 개인]. 실패 시 빈 DF.
    """
    days = days or config.PREDICT_FLOW_DAYS
    end = krx.business_day()
    start = krx.date_months_ago(0)  # placeholder; 실제 시작일 계산 아래
    start = krx.date_months_ago(max(1, days // 20))  # days 영업일 ≈ days/20 개월 여유

    def _compute() -> pd.DataFrame:
        cols = {}
        for label, investor in (("외국인", "외국인"), ("기관", "기관합계"), ("개인", "개인")):
            s = krx.net_purchases(market, start, end, investor)
            if not s.empty:
                cols[label] = s
        if not cols:
            return pd.DataFrame()
        return pd.DataFrame(cols)

    return cache.get_or_compute(f"flows_{market}_{end}_{days}", _compute)


def smart_money(flows: pd.DataFrame) -> pd.Series:
    """스마트머니(외국인+기관) 순매수 합계. 수급 스코어의 원지표."""
    if flows is None or flows.empty:
        return pd.Series(dtype=float)
    cols = [c for c in ("외국인", "기관") if c in flows.columns]
    if not cols:
        return pd.Series(dtype=float)
    return flows[cols].sum(axis=1)

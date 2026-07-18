"""종목 유니버스 조회.

퀀트 대상 종목 집합을 구성한다. 국내는 지수(코스피200·코스닥150) 구성종목을 사용한다.
미국 확장 시 여기에 US 유니버스(예: S&P500) 분기를 추가하면 된다.
"""
from __future__ import annotations

import pandas as pd

import config
from core import cache
from core.providers import krx


def get_universe(index_names: list[str] | None = None) -> pd.DataFrame:
    """선택한 지수들의 구성종목을 합쳐 반환.

    반환 DataFrame: columns=[ticker, market] (index_name 포함). 실패 시 빈 DF.
    """
    index_names = index_names or list(config.QUANT_UNIVERSE_INDICES)
    rows = []
    for name in index_names:
        code = config.QUANT_UNIVERSE_INDICES.get(name)
        if not code:
            continue
        market = config.QUANT_INDEX_MARKET.get(code, "KOSPI")
        tickers = cache.get_or_compute(
            f"universe_{code}_{krx.business_day()}",
            lambda code=code: pd.DataFrame({"ticker": krx.index_constituents(code)}),
        )
        for t in tickers.get("ticker", []):
            rows.append({"ticker": str(t), "market": market, "index": name})
    if not rows:
        return pd.DataFrame(columns=["ticker", "market", "index"])
    return pd.DataFrame(rows).drop_duplicates("ticker").reset_index(drop=True)

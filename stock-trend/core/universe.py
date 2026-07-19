"""종목 유니버스 조회.

퀀트/예측 대상 종목 집합을 구성한다. 국내는 지수(코스피200·코스닥150) 구성종목을 사용하되,
pykrx(국내망)가 안 될 때는 **금융위 API의 시총 상위 근사**로 폴백해 클라우드에서도 동작한다.
미국 확장 시 여기에 US 유니버스(예: S&P500) 분기를 추가하면 된다.
"""
from __future__ import annotations

import re

import pandas as pd

import config
from core import cache
from core import krx_api
from core.providers import krx


def _index_size(name: str) -> int:
    """지수명에서 편입 종목수 추정(코스피200→200, 코스닥150→150)."""
    m = re.search(r"(\d+)", name)
    return int(m.group(1)) if m else 200


def _constituents(name: str, code: str, market: str) -> list[str]:
    """지수 구성종목. pykrx(정확) → 금융위 시총상위 근사 순."""
    tickers = krx.index_constituents(code)
    if tickers:
        return [str(t).zfill(6) for t in tickers]
    # 폴백: 금융위 API 시총 상위 N (전역 접근, 근사)
    listing = krx_api.fetch_listing(market)
    if not listing.empty and "mktcap" in listing.columns:
        top = listing.sort_values("mktcap", ascending=False).head(_index_size(name))
        return [str(t).zfill(6) for t in top["ticker"]]
    return []


def get_universe(index_names: list[str] | None = None) -> pd.DataFrame:
    """선택한 지수들의 구성종목을 합쳐 반환.

    반환 DataFrame: columns=[ticker, market, index]. 실패 시 빈 DF.
    approx 여부는 index_constituents 성공 여부로 결정(폴백 시 시총 근사).
    """
    index_names = index_names or list(config.QUANT_UNIVERSE_INDICES)
    rows = []
    for name in index_names:
        code = config.QUANT_UNIVERSE_INDICES.get(name)
        if not code:
            continue
        market = config.QUANT_INDEX_MARKET.get(code, "KOSPI")
        df = cache.get_or_compute(
            f"universe_{code}_{krx.business_day()}",
            lambda name=name, code=code, market=market:
                pd.DataFrame({"ticker": _constituents(name, code, market)}),
        )
        for t in df.get("ticker", []):
            rows.append({"ticker": str(t), "market": market, "index": name})
    if not rows:
        return pd.DataFrame(columns=["ticker", "market", "index"])
    return pd.DataFrame(rows).drop_duplicates("ticker").reset_index(drop=True)

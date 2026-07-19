"""상승/하락 예측 랭킹 엔진.

blend/rank는 순수 함수(입력만으로 계산 → 테스트 용이).
build_ranking은 데이터 조회(추세·수급·매크로)를 묶어 실제 랭킹을 만든다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
import pandas as pd

import config
from core import data as data_mod
from core import flows as flows_mod
from core import macro as macro_mod
from core import cache
from core.providers import krx
from core import universe as universe_mod
from trend_service.engine import evaluate_price


# --------------------------------------------------------------------------
# 순수 계산 (네트워크 불필요, 테스트 대상)
# --------------------------------------------------------------------------
def _zscore(s: pd.Series, clip: float = 3.0) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    sd = s.std(ddof=0)
    if not sd or pd.isna(sd):
        return pd.Series(0.0, index=s.index)
    return ((s - s.mean()) / sd).clip(-clip, clip)


def blend(
    trend: pd.Series,
    flow: pd.Series,
    macro_z: float,
    weights: dict | None = None,
) -> pd.Series:
    """추세·수급 z-score와 매크로(공통)를 가중 합성한 예측 점수.

    trend: 종목별 추세점수(-100~100), flow: 종목별 수급 원지표, macro_z: -1~1 공통값.
    """
    weights = weights or config.PREDICT_WEIGHTS
    total = sum(weights.values()) or 1.0
    w = {k: v / total for k, v in weights.items()}
    idx = trend.index.union(flow.index)
    tz = _zscore(trend.reindex(idx))
    fz = _zscore(flow.reindex(idx))
    score = tz * w.get("trend", 0) + fz * w.get("flow", 0) + macro_z * w.get("macro", 0)
    return score.sort_values(ascending=False)


def split_top_bottom(score: pd.Series, top_n: int) -> tuple[pd.Series, pd.Series]:
    """상승 가능성 top N / 하락 가능성 top N(하위)."""
    ordered = score.sort_values(ascending=False)
    up = ordered.head(top_n)
    down = ordered.tail(top_n).sort_values()   # 낮은 순
    return up, down


# --------------------------------------------------------------------------
# 결과 컨테이너
# --------------------------------------------------------------------------
@dataclass
class RankingResult:
    up: pd.DataFrame = field(default_factory=pd.DataFrame)      # 상승 top N
    down: pd.DataFrame = field(default_factory=pd.DataFrame)    # 하락 top N
    macro: Optional[macro_mod.MacroRegime] = None
    universe_size: int = 0
    error: str = ""


# --------------------------------------------------------------------------
# 데이터 조회 + 조립
# --------------------------------------------------------------------------
def _trend_scores(tickers: list[str], period: str, progress: Callable | None) -> pd.Series:
    """종목별 추세판정(가격 코어) 점수. 날짜 캐시."""
    key = f"trendscores_{config.PREDICT_UNIVERSE}_{krx.business_day()}_{period}"
    cached = cache.load(key)
    if cached is not None and not cached.empty:
        return cached.iloc[:, 0]

    scores = {}
    n = len(tickers)
    for i, t in enumerate(tickers):
        try:
            stock = data_mod.get_stock_data(t, period)
            if not stock.ohlcv.empty:
                core = evaluate_price(stock.ohlcv)
                if core.indicators:
                    scores[t] = int(max(-100, min(100, core.bull - core.bear)))
        except Exception:
            pass
        if progress:
            progress((i + 1) / n)
    s = pd.Series(scores, dtype=float)
    if not s.empty:
        cache.save(key, s.to_frame("score"))
    return s


def build_ranking(
    period: str = "1y",
    weights: dict | None = None,
    top_n: int | None = None,
    progress: Callable | None = None,
) -> RankingResult:
    """코스피200 상승/하락 예측 랭킹을 만든다."""
    weights = weights or config.PREDICT_WEIGHTS
    top_n = top_n or config.PREDICT_TOP_N

    uni = universe_mod.get_universe([config.PREDICT_UNIVERSE])
    if uni.empty:
        return RankingResult(error="유니버스(코스피200) 조회 실패")
    tickers = [str(t).zfill(6) for t in uni["ticker"]]
    market = config.QUANT_INDEX_MARKET.get(
        config.QUANT_UNIVERSE_INDICES.get(config.PREDICT_UNIVERSE, ""), "KOSPI")

    trend = _trend_scores(tickers, period, progress)
    flow_df = flows_mod.get_flows(market)
    flow = flows_mod.smart_money(flow_df).reindex(trend.index) if not flow_df.empty else pd.Series(0.0, index=trend.index)
    regime = macro_mod.market_regime(period)

    if trend.empty:
        return RankingResult(macro=regime, universe_size=len(tickers),
                             error="추세점수 계산 실패(시세 조회 불가 — 국내망/pykrx 필요)")

    score = blend(trend, flow.fillna(0), regime.z, weights)
    up, down = split_top_bottom(score, top_n)

    def _frame(s: pd.Series) -> pd.DataFrame:
        df = pd.DataFrame({"ticker": s.index, "예측점수": s.values})
        df["종목명"] = [krx.ticker_name(t) or "-" for t in df["ticker"]]
        df["추세점수"] = [trend.get(t, np.nan) for t in df["ticker"]]
        if not flow_df.empty:
            for col in ("외국인", "기관", "개인"):
                if col in flow_df.columns:
                    df[col] = [flow_df[col].get(t, np.nan) for t in df["ticker"]]
        df.insert(0, "순위", range(1, len(df) + 1))
        return df

    return RankingResult(up=_frame(up), down=_frame(down), macro=regime,
                         universe_size=len(tickers))

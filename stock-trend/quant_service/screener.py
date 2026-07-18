"""퀀트 스크리너 — 팩터 합성점수로 종목을 랭킹·선정한다."""
from __future__ import annotations

import pandas as pd

import config
from quant_service import factors as fac


def _is_common_stock(ticker: str) -> bool:
    """보통주 여부(코드 끝자리 0). 우선주는 5/7/9 등으로 끝난다."""
    t = str(ticker)[:6]
    return t.isdigit() and t.endswith("0")


def screen(
    snapshot: pd.DataFrame,
    weights: dict | None = None,
    top_n: int | None = None,
    exclude_preferred: bool | None = None,
) -> pd.DataFrame:
    """스냅샷 → 상위 N 랭킹 DataFrame.

    반환 cols: rank, ticker, market, score, value_z, quality_z, momentum_z,
               PER, PBR, DIV, ROE, MOM, MKTCAP
    """
    weights = weights or config.QUANT_FACTOR_WEIGHTS
    top_n = top_n or config.QUANT_TOP_N
    if exclude_preferred is None:
        exclude_preferred = config.QUANT_EXCLUDE_PREFERRED

    if snapshot is None or snapshot.empty:
        return pd.DataFrame()

    df = snapshot.copy()
    if exclude_preferred:
        df = df[[_is_common_stock(t) for t in df.index]]
    if df.empty:
        return pd.DataFrame()

    factors = fac.compute_factors(df)
    score = fac.composite_score(factors, weights)

    out = pd.DataFrame(index=df.index)
    out["score"] = score
    out = out.join(factors)
    for col in ("PER", "PBR", "DIV", "ROE", "MOM", "MKTCAP", "market"):
        if col in df.columns:
            out[col] = df[col]
    out = out.sort_values("score", ascending=False).head(top_n)
    out.insert(0, "rank", range(1, len(out) + 1))
    out.insert(1, "ticker", out.index)
    return out.reset_index(drop=True)

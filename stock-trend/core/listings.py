"""종목명 ↔ 티커 매핑 (종목명 검색용).

소스 우선순위 (클라우드/해외에서도 되도록):
  1) 금융위 주식시세정보 API (전역 접근, DATA_GO_KR_API_KEY 필요)
  2) FinanceDataReader (KRX 전체목록)
  3) pykrx 유니버스(코스피200·코스닥150) 이름 — 최후 폴백
결과는 날짜 키로 디스크 캐시한다.
"""
from __future__ import annotations

import pandas as pd

from core import cache
from core import krx_api
from core.providers import krx


def _from_datagokr() -> pd.DataFrame:
    """금융위 API로 KOSPI+KOSDAQ 상장목록(전역 접근). 키 없으면 빈 DF."""
    if not krx_api.api_key():
        return pd.DataFrame()
    parts = [krx_api.fetch_listing("KOSPI"), krx_api.fetch_listing("KOSDAQ")]
    parts = [p for p in parts if not p.empty]
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts).drop_duplicates("ticker").reset_index(drop=True)
    return df[["ticker", "name"] + [c for c in ("market",) if c in df.columns]]


def _from_fdr() -> pd.DataFrame:
    try:
        import FinanceDataReader as fdr
    except Exception:
        return pd.DataFrame()
    try:
        df = fdr.StockListing("KRX")
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    code_col = next((c for c in ("Code", "Symbol", "종목코드") if c in df.columns), None)
    name_col = next((c for c in ("Name", "종목명") if c in df.columns), None)
    if not code_col or not name_col:
        return pd.DataFrame()
    out = pd.DataFrame({
        "ticker": df[code_col].astype(str).str.zfill(6),
        "name": df[name_col].astype(str),
    })
    if "Market" in df.columns:
        out["market"] = df["Market"].astype(str)
    return out.dropna().drop_duplicates("ticker").reset_index(drop=True)


def _from_pykrx_universe() -> pd.DataFrame:
    """폴백: 코스피200·코스닥150 종목명(제한적 커버리지)."""
    import config
    rows = []
    for name, code in config.QUANT_UNIVERSE_INDICES.items():
        for t in krx.index_constituents(code):
            nm = krx.ticker_name(t)
            if nm:
                rows.append({"ticker": str(t).zfill(6), "name": nm})
    return pd.DataFrame(rows).drop_duplicates("ticker") if rows else pd.DataFrame()


def get_listing() -> pd.DataFrame:
    """상장 종목목록(ticker, name[, market]). 실패 시 빈 DF. 날짜 키 디스크 캐시."""
    key = f"listing_{krx.business_day()}"

    def _compute() -> pd.DataFrame:
        for source in (_from_datagokr, _from_fdr, _from_pykrx_universe):
            df = source()
            if df is not None and not df.empty:
                return df
        return pd.DataFrame()

    return cache.get_or_compute(key, _compute)


def search(query: str, limit: int = 20) -> pd.DataFrame:
    """종목명/티커 부분일치 검색. 반환: [ticker, name] 상위 limit."""
    q = (query or "").strip()
    if not q:
        return pd.DataFrame(columns=["ticker", "name"])
    listing = get_listing()
    if listing.empty:
        return pd.DataFrame(columns=["ticker", "name"])
    mask = listing["name"].str.contains(q, case=False, na=False) | listing["ticker"].str.contains(q, na=False)
    return listing[mask].head(limit).reset_index(drop=True)


def name_to_ticker(name: str) -> str | None:
    """정확한 종목명 → 티커."""
    listing = get_listing()
    if listing.empty:
        return None
    hit = listing[listing["name"] == name]
    return str(hit.iloc[0]["ticker"]) if not hit.empty else None

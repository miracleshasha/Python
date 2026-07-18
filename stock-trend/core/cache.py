"""날짜 키 디스크 캐시.

대량 횡단면 조회(펀더멘털·시세 스냅샷)를 하루 단위로 캐싱해 반복 실행을 빠르게 한다.
저장 위치는 STOCK_TREND_DATA(환경변수) 또는 프로젝트 data/cache.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

import pandas as pd


def _cache_dir() -> Path:
    base = os.environ.get("STOCK_TREND_DATA")
    root = Path(base) if base else Path(__file__).resolve().parent.parent / "data"
    return root / "cache"


def _path(key: str) -> Path:
    safe = key.replace("/", "_").replace(":", "_")
    return _cache_dir() / f"{safe}.pkl"


def load(key: str) -> Optional[pd.DataFrame]:
    p = _path(key)
    if p.exists():
        try:
            return pd.read_pickle(p)
        except Exception:
            return None
    return None


def save(key: str, df: pd.DataFrame) -> None:
    p = _path(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_pickle(p)
    except Exception:
        pass


def get_or_compute(key: str, compute: Callable[[], pd.DataFrame]) -> pd.DataFrame:
    """캐시에 있으면 반환, 없으면 compute() 실행 후 저장.

    compute()가 빈 DataFrame을 주면 캐시하지 않는다(다음 시도에서 재조회).
    """
    cached = load(key)
    if cached is not None and not cached.empty:
        return cached
    df = compute()
    if df is not None and not df.empty:
        save(key, df)
    return df if df is not None else pd.DataFrame()

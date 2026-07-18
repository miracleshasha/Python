"""워치리스트(관심종목) 저장/관리.

여러 종목을 로컬 JSON에 저장해두고, 한 번에 판정·비교할 수 있게 한다.
DB 없이 파일 하나로 관리한다. 저장 위치는 STOCK_TREND_DATA 환경변수로 바꿀 수 있다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from core.markets import normalize_ticker


def _data_dir() -> Path:
    base = os.environ.get("STOCK_TREND_DATA")
    if base:
        return Path(base)
    # 기본: 프로젝트 stock-trend/data
    return Path(__file__).resolve().parent.parent / "data"


def watchlist_path() -> Path:
    return _data_dir() / "watchlist.json"


def load() -> list[str]:
    """저장된 티커 목록(원본 입력 형태)을 반환. 없으면 빈 리스트."""
    path = watchlist_path()
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as f:
            items = json.load(f)
        if isinstance(items, list):
            return [str(t) for t in items]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save(tickers: list[str]) -> None:
    """티커 목록을 저장(디렉터리 자동 생성)."""
    path = watchlist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(tickers, f, ensure_ascii=False, indent=2)


def _canonical(ticker: str) -> str:
    """중복 판정용 정규화 키(예: '005930' == '005930.KS')."""
    norm, _ = normalize_ticker(ticker)
    return norm.upper()


def add(ticker: str) -> list[str]:
    """티커 추가(정규화 기준 중복이면 무시). 갱신된 목록 반환."""
    ticker = ticker.strip()
    if not ticker:
        return load()
    items = load()
    keys = {_canonical(t) for t in items}
    if _canonical(ticker) not in keys:
        items.append(ticker)
        save(items)
    return items


def remove(ticker: str) -> list[str]:
    """티커 제거(정규화 기준 매칭). 갱신된 목록 반환."""
    key = _canonical(ticker)
    items = [t for t in load() if _canonical(t) != key]
    save(items)
    return items

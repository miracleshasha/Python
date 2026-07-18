"""스크리너 테스트 (합성 데이터, 네트워크 불필요)."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from quant_service import screener  # noqa: E402


def _snapshot():
    return pd.DataFrame({
        "PER": [5.0, 10.0, 20.0, 40.0, 6.0],
        "PBR": [0.5, 1.0, 2.0, 4.0, 0.6],
        "DIV": [4.0, 3.0, 2.0, 1.0, 3.5],
        "ROE": [0.20, 0.15, 0.08, 0.03, 0.18],
        "MOM": [0.30, 0.10, -0.05, -0.20, 0.25],
        "MKTCAP": [1e12] * 5,
        "market": ["KOSPI"] * 5,
    }, index=["000660", "000670", "000680", "000690", "000665"])  # 000665=우선주(끝 5)


def test_screen_ranks_and_topn():
    res = screener.screen(_snapshot(), top_n=3, exclude_preferred=False)
    assert len(res) == 3
    assert list(res.columns[:3]) == ["rank", "ticker", "score"]
    assert "market" in res.columns
    # 점수 내림차순
    assert res["score"].is_monotonic_decreasing
    assert res.iloc[0]["rank"] == 1


def test_exclude_preferred():
    res = screener.screen(_snapshot(), top_n=10, exclude_preferred=True)
    # 000665(우선주, 끝자리 5) 제외
    assert "000665" not in set(res["ticker"])
    res_all = screener.screen(_snapshot(), top_n=10, exclude_preferred=False)
    assert "000665" in set(res_all["ticker"])


def test_empty_snapshot():
    assert screener.screen(pd.DataFrame()).empty


def test_best_stock_on_top():
    # 000660: 저PER·저PBR·고배당·고ROE·고모멘텀 → 1등 기대
    res = screener.screen(_snapshot(), top_n=5, exclude_preferred=False)
    assert res.iloc[0]["ticker"] == "000660"

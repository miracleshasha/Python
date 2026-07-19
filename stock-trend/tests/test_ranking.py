"""예측 랭킹 순수 로직 테스트 (합성 데이터, 네트워크 불필요)."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from prediction_service import ranking  # noqa: E402


def test_blend_orders_by_trend_and_flow():
    trend = pd.Series({"A": 80, "B": 0, "C": -80})
    flow = pd.Series({"A": 100, "B": 0, "C": -100})
    score = ranking.blend(trend, flow, macro_z=0.0, weights={"trend": 50, "flow": 30, "macro": 20})
    assert score.index[0] == "A"      # 최상위
    assert score.index[-1] == "C"     # 최하위


def test_macro_shifts_but_keeps_order():
    trend = pd.Series({"A": 50, "B": -50})
    flow = pd.Series({"A": 10, "B": -10})
    s_pos = ranking.blend(trend, flow, macro_z=1.0)
    s_neg = ranking.blend(trend, flow, macro_z=-1.0)
    # 매크로는 공통 → 순서 유지, 전체 점수만 이동
    assert list(s_pos.index) == list(s_neg.index)
    assert s_pos["A"] > s_neg["A"]


def test_split_top_bottom():
    score = pd.Series({t: v for t, v in zip("ABCDEF", [5, 4, 3, 2, 1, 0])})
    up, down = ranking.split_top_bottom(score, top_n=2)
    assert list(up.index) == ["A", "B"]
    assert list(down.index) == ["F", "E"]   # 낮은 순


def test_blend_handles_missing_flow():
    trend = pd.Series({"A": 30, "B": 10, "C": -20})
    flow = pd.Series({"A": 5}, dtype=float)   # 일부만
    score = ranking.blend(trend, flow.reindex(trend.index).fillna(0), macro_z=0.0)
    assert len(score) == 3
    assert score.index[0] == "A"

"""백테스트 성질 테스트 (합성 데이터)."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from trend_service import backtest as bt  # noqa: E402


def _ohlcv(closes):
    idx = pd.date_range("2020-01-01", periods=len(closes), freq="D")
    c = pd.Series(closes, index=idx, dtype=float)
    rng = np.random.default_rng(1)
    return pd.DataFrame(
        {"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c,
         "Volume": pd.Series(rng.integers(1e6, 3e6, len(closes)), index=idx, dtype=float)}
    )


def test_uptrend_bull_signals_profitable():
    # 꾸준한 상승장: 상승 신호의 평균 forward 수익률은 양수여야 한다.
    df = _ohlcv(np.linspace(100, 300, 300))
    res = bt.run(df, horizon=20)
    assert res.total_signals > 0
    assert res.bull.count > 0
    assert res.bull.avg_return > 0
    assert res.bull.hit_rate > 0.5


def test_downtrend_bear_signals_hit():
    # 꾸준한 하락장: 하락 신호가 잡히고 방향 적중률이 높아야 한다.
    df = _ohlcv(np.linspace(300, 100, 300))
    res = bt.run(df, horizon=20)
    assert res.bear.count > 0
    assert res.bear.hit_rate > 0.5


def test_result_columns():
    df = _ohlcv(np.linspace(100, 200, 200))
    res = bt.run(df, horizon=15)
    assert res.horizon == 15
    if not res.trades.empty:
        assert {"idx", "verdict", "score", "fwd_return"} <= set(res.trades.columns)

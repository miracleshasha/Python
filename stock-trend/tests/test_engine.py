"""판정 엔진 테스트 (합성 데이터, 네트워크 불필요)."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from trend_service.data import StockData  # noqa: E402
from trend_service.engine import evaluate_price, quick_verdict, score_to_verdict  # noqa: E402


def _ohlcv(closes):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    c = pd.Series(closes, index=idx, dtype=float)
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c,
         "Volume": pd.Series(rng.integers(1e6, 3e6, len(closes)), index=idx, dtype=float)}
    )


def test_score_to_verdict_thresholds():
    assert score_to_verdict(50) == "상승"
    assert score_to_verdict(-50) == "하락"
    assert score_to_verdict(0) == "중립"


def test_uptrend_is_bullish():
    df = _ohlcv(np.linspace(100, 200, 150))
    verdict, score = quick_verdict(df)
    assert verdict == "상승"
    assert score > 0


def test_downtrend_is_bearish():
    df = _ohlcv(np.linspace(200, 100, 150))
    verdict, score = quick_verdict(df)
    assert verdict == "하락"
    assert score < 0


def test_insufficient_data_is_neutral():
    df = _ohlcv(np.linspace(100, 110, 10))
    verdict, score = quick_verdict(df)
    assert verdict == "중립"
    assert score == 0


def test_evaluate_price_is_point_in_time():
    # 앞부분 슬라이스 판정이 뒤 데이터에 영향받지 않아야 한다(look-ahead 없음).
    full = _ohlcv(np.concatenate([np.linspace(100, 200, 100), np.linspace(200, 100, 100)]))
    early = full.iloc[:120]
    e1 = evaluate_price(early)
    e2 = evaluate_price(full.iloc[:120].copy())
    assert (e1.bull, e1.bear) == (e2.bull, e2.bear)


def test_evaluate_price_returns_indicators():
    df = _ohlcv(np.linspace(100, 200, 150))
    core = evaluate_price(df)
    assert {"ma", "rsi", "macd", "obv", "volume"} <= set(core.indicators.keys())

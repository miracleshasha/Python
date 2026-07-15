"""지표 계산 단위 테스트 (합성 데이터, 네트워크 불필요)."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

# stock-trend 루트를 import 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from trend_service import indicators as ind  # noqa: E402


def _series(values):
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D")
    return pd.Series(values, index=idx, dtype=float)


def _ohlcv(closes, volumes):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame(
        {"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c,
         "Volume": pd.Series(volumes, index=idx, dtype=float)}
    )


def test_moving_averages_basic():
    s = _series(list(range(1, 31)))  # 1..30
    ma = ind.moving_averages(s, [5])
    # 마지막 5일(26..30) 평균 = 28
    assert ma["MA5"].iloc[-1] == pytest.approx(28.0)
    # 초반은 NaN
    assert pd.isna(ma["MA5"].iloc[3])


def test_ma_slope_direction():
    up = _series(list(range(1, 21)))       # 상승
    down = _series(list(range(20, 0, -1)))  # 하락
    assert ind.ma_slope(up, lookback=5) > 0
    assert ind.ma_slope(down, lookback=5) < 0


def test_detect_cross_golden_and_dead():
    # 단기선이 장기선을 상향 돌파
    short = _series([1, 2, 3, 10])
    long = _series([5, 5, 5, 5])
    assert ind.detect_cross(short, long) == "golden"
    # 하향 돌파
    short2 = _series([10, 9, 8, 1])
    assert ind.detect_cross(short2, long) == "dead"
    # 교차 없음
    assert ind.detect_cross(_series([1, 1, 1, 1]), long) is None


def test_rsi_all_gains_is_100():
    s = _series(list(range(1, 40)))  # 계속 상승
    r = ind.rsi(s)
    assert r.iloc[-1] == pytest.approx(100.0)


def test_rsi_range_bounds():
    rng = np.random.default_rng(0)
    s = _series(np.cumsum(rng.normal(0, 1, 100)) + 100)
    r = ind.rsi(s).dropna()
    assert (r >= 0).all() and (r <= 100).all()


def test_macd_shapes():
    s = _series(np.linspace(100, 200, 60))
    m = ind.macd(s)
    assert set(m.columns) == {"MACD", "Signal", "Hist"}
    # 꾸준한 상승이면 MACD > 0
    assert m["MACD"].iloc[-1] > 0


def test_obv_accumulates_on_up_days():
    df = _ohlcv([10, 11, 12, 11], [100, 200, 300, 400])
    o = ind.obv(df)
    # day2: +200, day3: +300, day4: -400 → 100
    assert o.iloc[-1] == pytest.approx(100.0)


def test_bollinger_and_squeeze():
    # 변동성 큰 구간 후 아주 잔잔한 구간 → 마지막은 스퀴즈
    noisy = list(np.random.default_rng(1).normal(100, 5, 40))
    calm = [100.0] * 40
    s = _series(noisy + calm)
    bb = ind.bollinger(s)
    assert {"Mid", "Upper", "Lower", "Width"} <= set(bb.columns)
    assert ind.is_squeeze(bb) is True


def test_volume_signal_quadrants():
    up_vol = ind.volume_signal(_ohlcv([10, 11], [100, 200]))
    assert up_vol["price_up"] is True
    assert "건전한 상승" in up_vol["label"]


def test_bearish_divergence_detected():
    # 가격은 뒤 구간이 더 높은 고점, 지표는 뒤 구간이 낮은 고점
    price = _series([1, 5, 2, 6, 3, 7, 4, 8, 5, 9,
                     10, 8, 11, 7, 12, 6, 13, 5, 14, 4])
    indicator = _series([1, 9, 2, 8, 3, 7, 4, 6, 5, 5,
                         5, 4, 5, 3, 5, 2, 5, 1, 5, 0])
    assert ind.bearish_divergence(price, indicator, lookback=20) is True

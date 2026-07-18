"""팩터 계산 테스트 (합성 데이터, 네트워크 불필요)."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from quant_service import factors as fac  # noqa: E402


def _snapshot():
    # 4개 종목: A=저평가/고ROE/고모멘텀(최고), D=고평가/저ROE/저모멘텀(최저)
    return pd.DataFrame({
        "PER": [5.0, 10.0, 20.0, 40.0],
        "PBR": [0.5, 1.0, 2.0, 4.0],
        "DIV": [4.0, 3.0, 2.0, 1.0],
        "ROE": [0.20, 0.15, 0.08, 0.03],
        "MOM": [0.30, 0.10, -0.05, -0.20],
    }, index=["A", "B", "C", "D"])


def test_zscore_basic():
    z = fac.zscore(pd.Series([1.0, 2.0, 3.0]))
    assert abs(z.mean()) < 1e-9
    assert z.iloc[0] < 0 < z.iloc[-1]


def test_zscore_constant_is_zero():
    z = fac.zscore(pd.Series([5.0, 5.0, 5.0]))
    assert (z == 0).all()


def test_zscore_clip():
    z = fac.zscore(pd.Series([0, 0, 0, 0, 100]), clip=2.0)
    assert z.max() <= 2.0 and z.min() >= -2.0


def test_positive_inverse_excludes_nonpositive():
    inv = fac._positive_inverse(pd.Series([10.0, -5.0, 0.0]))
    assert inv.iloc[0] == 0.1
    assert pd.isna(inv.iloc[1]) and pd.isna(inv.iloc[2])


def test_compute_factors_shape_and_direction():
    f = fac.compute_factors(_snapshot())
    assert set(f.columns) == {"value_z", "quality_z", "momentum_z"}
    # A는 모든 팩터 최상위
    assert f.loc["A", "quality_z"] == f["quality_z"].max()
    assert f.loc["A", "momentum_z"] == f["momentum_z"].max()
    assert f.loc["A", "value_z"] == f["value_z"].max()


def test_composite_score_ranking():
    f = fac.compute_factors(_snapshot())
    score = fac.composite_score(f, {"value": 40, "quality": 30, "momentum": 30})
    # A가 1등, D가 꼴등
    assert score.idxmax() == "A"
    assert score.idxmin() == "D"


def test_composite_weight_emphasis():
    f = fac.compute_factors(_snapshot())
    # 모멘텀만 100% → 모멘텀 최고인 A가 최고점
    s = fac.composite_score(f, {"value": 0, "quality": 0, "momentum": 100})
    assert s.idxmax() == "A"

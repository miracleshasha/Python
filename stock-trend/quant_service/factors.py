"""팩터 계산 (순수 함수).

원지표 스냅샷(PER/PBR/DIV/ROE/MOM)을 받아 밸류·퀄리티·모멘텀 팩터의
횡단면 z-score를 만든다. 네트워크/상태 비의존 → 단위 테스트 용이.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config


def zscore(s: pd.Series, clip: float | None = None) -> pd.Series:
    """횡단면 z-score. 표준편차 0/결측이면 0. 이상치는 ±clip으로 클리핑."""
    clip = config.QUANT_ZSCORE_CLIP if clip is None else clip
    s = pd.to_numeric(s, errors="coerce")
    sd = s.std(ddof=0)
    if not sd or pd.isna(sd):
        return pd.Series(0.0, index=s.index)
    z = (s - s.mean()) / sd
    return z.clip(-clip, clip)


def _positive_inverse(s: pd.Series) -> pd.Series:
    """1/x (x>0만 유효, 그 외 NaN). 어닝일드·북일드용."""
    s = pd.to_numeric(s, errors="coerce")
    inv = 1.0 / s.where(s > 0)
    return inv.replace([np.inf, -np.inf], np.nan)


def compute_factors(snapshot: pd.DataFrame) -> pd.DataFrame:
    """스냅샷 → 팩터 z-score DataFrame.

    반환 cols: value_z, quality_z, momentum_z (index=ticker).
    - value: 어닝일드(1/PER)·북일드(1/PBR)·배당(DIV)의 z 평균
    - quality: ROE의 z
    - momentum: MOM의 z
    """
    idx = snapshot.index
    ey_z = zscore(_positive_inverse(snapshot.get("PER", pd.Series(index=idx, dtype=float))))
    by_z = zscore(_positive_inverse(snapshot.get("PBR", pd.Series(index=idx, dtype=float))))
    div_z = zscore(snapshot.get("DIV", pd.Series(index=idx, dtype=float)))
    value_z = pd.concat([ey_z, by_z, div_z], axis=1).mean(axis=1, skipna=True)

    quality_z = zscore(snapshot.get("ROE", pd.Series(index=idx, dtype=float)))
    momentum_z = zscore(snapshot.get("MOM", pd.Series(index=idx, dtype=float)))

    return pd.DataFrame({
        "value_z": value_z,
        "quality_z": quality_z,
        "momentum_z": momentum_z,
    }, index=idx)


def composite_score(factors: pd.DataFrame, weights: dict | None = None) -> pd.Series:
    """가중합 합성점수. weights 합이 100이 아니어도 정규화. 결측 z는 중립(0)."""
    weights = weights or config.QUANT_FACTOR_WEIGHTS
    total = sum(weights.values()) or 1.0
    w = {k: v / total for k, v in weights.items()}
    score = (
        factors["value_z"].fillna(0) * w.get("value", 0)
        + factors["quality_z"].fillna(0) * w.get("quality", 0)
        + factors["momentum_z"].fillna(0) * w.get("momentum", 0)
    )
    return score

"""기술적 지표 계산 (순수 함수).

모든 함수는 pandas Series/DataFrame을 입력받아 계산 결과를 반환한다.
네트워크/상태에 의존하지 않으므로 단위 테스트가 쉽다.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

import config


# --------------------------------------------------------------------------
# 이동평균
# --------------------------------------------------------------------------
def moving_averages(close: pd.Series, periods=None) -> pd.DataFrame:
    """기간별 단순이동평균(SMA)을 컬럼으로 담은 DataFrame 반환."""
    periods = periods or config.MA_PERIODS
    out = pd.DataFrame(index=close.index)
    for p in periods:
        out[f"MA{p}"] = close.rolling(window=p, min_periods=p).mean()
    return out


def ma_slope(ma: pd.Series, lookback: int = None) -> float:
    """이동평균의 최근 기울기를 정규화 값으로 반환.

    (현재값 - lookback일 전 값) / lookback일 전 값.
    +면 우상향, -면 우하향, 0 근처면 평평(경고 구간).
    데이터가 부족하면 0.0.
    """
    lookback = lookback or config.MA_SLOPE_LOOKBACK
    s = ma.dropna()
    if len(s) <= lookback:
        return 0.0
    past = s.iloc[-1 - lookback]
    if past == 0 or pd.isna(past):
        return 0.0
    return float((s.iloc[-1] - past) / abs(past))


def detect_cross(short: pd.Series, long: pd.Series) -> Optional[str]:
    """단기선-장기선의 최근 교차 방향 판정.

    반환: 'golden'(상향돌파) / 'dead'(하향돌파) / None(최근 교차 없음).
    마지막 2개 봉만 비교해 '방금' 발생한 크로스를 잡는다.
    """
    df = pd.concat([short, long], axis=1).dropna()
    if len(df) < 2:
        return None
    s_prev, l_prev = df.iloc[-2, 0], df.iloc[-2, 1]
    s_now, l_now = df.iloc[-1, 0], df.iloc[-1, 1]
    if s_prev <= l_prev and s_now > l_now:
        return "golden"
    if s_prev >= l_prev and s_now < l_now:
        return "dead"
    return None


# --------------------------------------------------------------------------
# 거래량 / OBV
# --------------------------------------------------------------------------
def volume_signal(df: pd.DataFrame) -> dict:
    """가격 방향 × 거래량 증감 4분면 해석.

    반환 dict:
      price_up: 최근 종가가 전일 대비 상승했는지
      volume_ratio: 최근 거래량 / 20일 평균
      surge: 급증 여부(config.VOLUME_SURGE_RATIO 기준)
      label: 사람이 읽을 해석 문자열
    """
    if len(df) < 2:
        return {"price_up": False, "volume_ratio": 0.0, "surge": False, "label": "데이터 부족"}

    close = df["Close"]
    vol = df["Volume"]
    price_up = bool(close.iloc[-1] > close.iloc[-2])
    avg_vol = vol.rolling(config.VOLUME_AVG_WINDOW, min_periods=1).mean().iloc[-1]
    ratio = float(vol.iloc[-1] / avg_vol) if avg_vol else 0.0
    vol_up = bool(vol.iloc[-1] > vol.iloc[-2])
    surge = ratio >= config.VOLUME_SURGE_RATIO

    if price_up and vol_up:
        label = "상승 + 거래량 증가 → 건전한 상승"
    elif price_up and not vol_up:
        label = "상승 + 거래량 감소 → 상승 동력 약화, 고점 경계"
    elif not price_up and vol_up:
        label = "하락 + 거래량 급증 → 투매 가능, 바닥 근처일 수 있음"
    else:
        label = "하락 + 거래량 감소 → 매물 소진, 반등 준비"

    return {"price_up": price_up, "volume_ratio": ratio, "surge": surge, "label": label}


def obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume 누적 시계열."""
    close = df["Close"]
    vol = df["Volume"]
    direction = np.sign(close.diff().fillna(0.0))
    return (direction * vol).cumsum()


# --------------------------------------------------------------------------
# RSI
# --------------------------------------------------------------------------
def rsi(close: pd.Series, period: int = None) -> pd.Series:
    """Wilder 방식 RSI."""
    period = period or config.RSI_PERIOD
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100 - (100 / (1 + rs))
    # avg_loss가 0이면(전부 상승) RSI=100
    out = out.where(avg_loss != 0, 100.0)
    return out


# --------------------------------------------------------------------------
# MACD
# --------------------------------------------------------------------------
def macd(close: pd.Series, fast=None, slow=None, signal=None) -> pd.DataFrame:
    """MACD/시그널/히스토그램."""
    fast = fast or config.MACD_FAST
    slow = slow or config.MACD_SLOW
    signal = signal or config.MACD_SIGNAL
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    line = ema_fast - ema_slow
    sig = line.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame({"MACD": line, "Signal": sig, "Hist": line - sig})


# --------------------------------------------------------------------------
# 볼린저밴드
# --------------------------------------------------------------------------
def bollinger(close: pd.Series, period=None, num_std=None) -> pd.DataFrame:
    """볼린저밴드 상/중/하단 + 밴드폭."""
    period = period or config.BB_PERIOD
    num_std = num_std or config.BB_STD
    mid = close.rolling(period, min_periods=period).mean()
    std = close.rolling(period, min_periods=period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    width = (upper - lower) / mid
    return pd.DataFrame({"Mid": mid, "Upper": upper, "Lower": lower, "Width": width})


def envelope(close: pd.Series, period: int = None, pct: float = None) -> pd.DataFrame:
    """엔벨로프: 이동평균선 ± 일정 비율(%) 밴드.

    볼린저밴드가 변동성(표준편차) 기반인 것과 달리, 엔벨로프는 고정 비율 기반이라
    추세 이탈/과열 구간을 직관적으로 본다.
    """
    period = period or config.ENVELOPE_PERIOD
    pct = pct if pct is not None else config.ENVELOPE_PCT
    mid = close.rolling(period, min_periods=period).mean()
    return pd.DataFrame({"Mid": mid, "Upper": mid * (1 + pct), "Lower": mid * (1 - pct)})


def is_squeeze(bb: pd.DataFrame, quantile: float = None) -> bool:
    """현재 밴드폭이 과거 대비 하위 분위 이하면 스퀴즈(변동성 수축)."""
    quantile = quantile if quantile is not None else config.BB_SQUEEZE_QUANTILE
    w = bb["Width"].dropna()
    if len(w) < config.BB_PERIOD:
        return False
    return bool(w.iloc[-1] <= w.quantile(quantile))


# --------------------------------------------------------------------------
# 다이버전스
# --------------------------------------------------------------------------
def bearish_divergence(price: pd.Series, indicator: pd.Series, lookback: int = None) -> bool:
    """약세 다이버전스: 가격은 신고가인데 보조지표는 고점이 낮아짐.

    최근 lookback 구간을 반으로 나눠 각 구간 최고점을 비교한다.
    """
    lookback = lookback or config.DIVERGENCE_LOOKBACK
    df = pd.concat([price, indicator], axis=1).dropna()
    if len(df) < lookback:
        return False
    recent = df.iloc[-lookback:]
    half = lookback // 2
    p_first, p_second = recent.iloc[:half, 0], recent.iloc[half:, 0]
    i_first, i_second = recent.iloc[:half, 1], recent.iloc[half:, 1]
    price_higher_high = p_second.max() > p_first.max()
    indicator_lower_high = i_second.max() < i_first.max()
    return bool(price_higher_high and indicator_lower_high)


def bullish_divergence(price: pd.Series, indicator: pd.Series, lookback: int = None) -> bool:
    """강세 다이버전스: 가격은 신저가인데 보조지표는 저점이 높아짐."""
    lookback = lookback or config.DIVERGENCE_LOOKBACK
    df = pd.concat([price, indicator], axis=1).dropna()
    if len(df) < lookback:
        return False
    recent = df.iloc[-lookback:]
    half = lookback // 2
    p_first, p_second = recent.iloc[:half, 0], recent.iloc[half:, 0]
    i_first, i_second = recent.iloc[:half, 1], recent.iloc[half:, 1]
    price_lower_low = p_second.min() < p_first.min()
    indicator_higher_low = i_second.min() > i_first.min()
    return bool(price_lower_low and indicator_higher_low)

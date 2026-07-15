"""추세 판정 엔진.

지표 계산 결과와 시장심리를 사용자의 진입/청산 체크리스트 규칙으로 평가해
상승/하락/중립 판정과 그 근거를 만든다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

import config
from trend_service import data as data_mod
from trend_service import indicators as ind


@dataclass
class Reason:
    """판정 근거 한 줄."""
    key: str
    label: str          # 사람이 읽을 설명
    direction: str      # 'bull' | 'bear' | 'neutral' | 'na'
    detail: str = ""


@dataclass
class TrendResult:
    verdict: str                       # '상승' | '하락' | '중립'
    score: int                         # -100 ~ +100
    reasons: list[Reason] = field(default_factory=list)
    indicators: dict = field(default_factory=dict)  # 차트/표시용 계산 결과


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def analyze(stock: data_mod.StockData, period: str = config.DEFAULT_PERIOD) -> TrendResult:
    """종목 데이터를 받아 추세를 판정한다."""
    df = stock.ohlcv
    reasons: list[Reason] = []

    if df is None or len(df) < config.MA_PERIODS[0] + 2:
        return TrendResult(
            verdict="중립",
            score=0,
            reasons=[Reason("insufficient_data", "데이터가 부족합니다(신규 상장 등)", "na")],
            indicators={},
        )

    close = df["Close"]
    mas = ind.moving_averages(close)
    ma20 = mas.get(f"MA{config.MA_PERIODS[0]}")
    ma60 = mas.get(f"MA{config.MA_PERIODS[1]}")

    rsi_s = ind.rsi(close)
    macd_df = ind.macd(close)
    bb = ind.bollinger(close)
    obv_s = ind.obv(df)
    vol = ind.volume_signal(df)

    bull_score = 0
    bear_score = 0

    # ---- 상승 근거 ----
    slope60 = ind.ma_slope(ma60) if ma60 is not None else 0.0
    if slope60 > 0:
        bull_score += config.BULL_WEIGHTS["ma60_slope_up"]
        reasons.append(Reason("ma60_slope_up", "60일선 기울기 우상향", "bull",
                              f"기울기 {slope60:+.2%}"))
    elif slope60 < 0:
        bear_score += config.BEAR_WEIGHTS["ma60_slope_down"]
        reasons.append(Reason("ma60_slope_down", "60일선 기울기 하락(꺾임)", "bear",
                              f"기울기 {slope60:+.2%}"))
    else:
        reasons.append(Reason("ma60_slope_flat", "60일선 기울기 평평 → 경고 구간", "neutral"))

    above_ma20 = bool(ma20 is not None and close.iloc[-1] > ma20.iloc[-1])
    if above_ma20 and vol["surge"]:
        bull_score += config.BULL_WEIGHTS["above_ma20_with_volume"]
        reasons.append(Reason("above_ma20_with_volume",
                              "20일선 위 종가 + 거래량 급증", "bull",
                              f"거래량 {vol['volume_ratio']:.0%} vs 20일 평균"))
    elif above_ma20:
        reasons.append(Reason("above_ma20", "20일선 위 종가(거래량 평범)", "bull",
                              f"거래량 {vol['volume_ratio']:.0%}"))

    # 20일선 이탈 + 회복 실패 (하락)
    if ma20 is not None and len(df) >= 2:
        broke = close.iloc[-2] < ma20.iloc[-2]
        not_recovered = close.iloc[-1] < ma20.iloc[-1]
        if broke and not_recovered:
            bear_score += config.BEAR_WEIGHTS["break_ma20"]
            reasons.append(Reason("break_ma20", "20일선 이탈 후 회복 실패", "bear"))

    # 크로스
    if ma20 is not None and ma60 is not None:
        cross = ind.detect_cross(ma20, ma60)
        if cross == "golden":
            bull_score += config.BULL_WEIGHTS["golden_cross"]
            reasons.append(Reason("golden_cross", "골든크로스(20>60) 발생", "bull"))
        elif cross == "dead":
            bear_score += config.BEAR_WEIGHTS["dead_cross"]
            reasons.append(Reason("dead_cross", "데드크로스(20<60) 발생", "bear"))

    # ---- 하락 근거: 다이버전스 ----
    if ind.bearish_divergence(close, rsi_s):
        bear_score += config.BEAR_WEIGHTS["bearish_divergence"]
        reasons.append(Reason("rsi_divergence", "약세 다이버전스(가격 신고가 vs RSI 고점 낮아짐)", "bear"))
    elif ind.bearish_divergence(close, obv_s):
        bear_score += config.BEAR_WEIGHTS["bearish_divergence"]
        reasons.append(Reason("obv_divergence", "약세 다이버전스(가격 신고가 vs OBV 못 따라옴)", "bear"))
    elif ind.bullish_divergence(close, rsi_s):
        bull_score += config.BULL_WEIGHTS["ma60_slope_up"] // 2
        reasons.append(Reason("bullish_divergence", "강세 다이버전스(가격 신저가 vs RSI 저점 높아짐)", "bull"))

    # ---- 시장심리: VIX / SOX ----
    vix_df = data_mod.get_market_index(config.MARKET_INDEX_VIX, period)
    sox_df = data_mod.get_market_index(config.MARKET_INDEX_SOX, period)
    vix_spike = False
    sox_drop = False

    if not vix_df.empty and len(vix_df) >= 2:
        vix_now = float(vix_df["Close"].iloc[-1])
        vix_prev = float(vix_df["Close"].iloc[-2])
        vix_change = (vix_now - vix_prev) / vix_prev if vix_prev else 0.0
        vix_spike = vix_change >= config.VIX_SPIKE_PCT
        if vix_now <= config.VIX_NORMAL + 5 and vix_change <= 0:
            bull_score += config.BULL_WEIGHTS["vix_calm"]
            reasons.append(Reason("vix_calm", f"VIX 안정({vix_now:.1f}, 하락 중)", "bull"))
        elif vix_now >= config.VIX_FEAR:
            reasons.append(Reason("vix_fear", f"VIX 공포 구간({vix_now:.1f})", "bear",
                                  "역발상 매수 타이밍이 나올 수 있는 구간"))
    else:
        reasons.append(Reason("vix_na", "VIX 데이터 없음", "na"))

    if not sox_df.empty and len(sox_df) >= config.MA_PERIODS[0]:
        sox_close = sox_df["Close"]
        sox_ma20 = sox_close.rolling(config.MA_PERIODS[0]).mean().iloc[-1]
        sox_above = sox_close.iloc[-1] > sox_ma20
        sox_change = sox_close.pct_change().iloc[-1]
        sox_drop = bool(sox_change <= -0.03)
        if sox_above:
            bull_score += config.BULL_WEIGHTS["sox_above_ma20"]
            reasons.append(Reason("sox_above_ma20", "SOX(반도체) 20일선 위", "bull"))
        else:
            reasons.append(Reason("sox_below_ma20", "SOX(반도체) 20일선 아래", "bear"))
    else:
        reasons.append(Reason("sox_na", "SOX 데이터 없음", "na"))

    if vix_spike and sox_drop:
        bear_score += config.BEAR_WEIGHTS["vix_spike_sox_drop"]
        reasons.append(Reason("vix_spike_sox_drop", "VIX 급등 + SOX 급락 동반", "bear"))

    # ---- 외국인 수급 (국내 종목, pykrx 있을 때만) ----
    if stock.is_korean:
        netbuy = data_mod.get_foreign_netbuy(stock.ticker)
        if netbuy is not None and len(netbuy) >= 5:
            last3 = netbuy.tail(3)
            last5 = netbuy.tail(5)
            if (last3 > 0).all():
                bull_score += config.BULL_WEIGHTS["foreign_net_buy"]
                reasons.append(Reason("foreign_net_buy", "외국인 3일 연속 순매수", "bull"))
            elif (last5 < 0).all():
                bear_score += config.BEAR_WEIGHTS["foreign_net_sell"]
                reasons.append(Reason("foreign_net_sell", "외국인 5일 연속 순매도", "bear"))
        else:
            reasons.append(Reason("foreign_na", "외국인 수급 데이터 없음(pykrx 미설치)", "na"))

    # ---- 종합 스코어 ----
    raw = bull_score - bear_score
    score = int(_clamp(raw, -100, 100))
    if score >= config.VERDICT_BULL_THRESHOLD:
        verdict = "상승"
    elif score <= config.VERDICT_BEAR_THRESHOLD:
        verdict = "하락"
    else:
        verdict = "중립"

    # 거래량 4분면 해석도 근거에 추가(중립 정보)
    reasons.append(Reason("volume_quadrant", vol["label"], "neutral"))

    indicators_out = {
        "close": close,
        "ma": mas,
        "rsi": rsi_s,
        "macd": macd_df,
        "bollinger": bb,
        "obv": obv_s,
        "volume": df["Volume"],
        "squeeze": ind.is_squeeze(bb),
        "bull_score": bull_score,
        "bear_score": bear_score,
    }

    return TrendResult(verdict=verdict, score=score, reasons=reasons, indicators=indicators_out)

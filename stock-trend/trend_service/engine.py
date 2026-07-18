"""추세 판정 엔진.

두 계층으로 나뉜다:
- evaluate_price(df): 가격/거래량만 쓰는 **포인트인타임** 판정 코어(네트워크 불필요).
  백테스트가 과거 시점마다 look-ahead 없이 호출한다.
- analyze(stock): evaluate_price 위에 시장맥락(VIX/SOX/외국인 수급, 최신 시점 전용)을 얹어
  최종 판정을 만든다. 실시간 단일 분석용.
"""
from __future__ import annotations

from dataclasses import dataclass, field

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
class PriceEval:
    """가격 기반 코어 판정 결과."""
    bull: int
    bear: int
    reasons: list[Reason] = field(default_factory=list)
    indicators: dict = field(default_factory=dict)


@dataclass
class TrendResult:
    verdict: str                       # '상승' | '하락' | '중립'
    score: int                         # -100 ~ +100
    reasons: list[Reason] = field(default_factory=list)
    indicators: dict = field(default_factory=dict)  # 차트/표시용 계산 결과


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def score_to_verdict(score: int) -> str:
    if score >= config.VERDICT_BULL_THRESHOLD:
        return "상승"
    if score <= config.VERDICT_BEAR_THRESHOLD:
        return "하락"
    return "중립"


# 코어 판정에 필요한 최소 봉 수(MA20 + 다이버전스 여유)
MIN_BARS = config.MA_PERIODS[0] + 2


def evaluate_price(df: pd.DataFrame) -> PriceEval:
    """가격/거래량만으로 상승·하락 근거 점수를 계산한다(포인트인타임, 네트워크 X).

    df는 해당 시점까지의 OHLCV. 미래 데이터를 참조하지 않는다.
    """
    reasons: list[Reason] = []
    if df is None or len(df) < MIN_BARS:
        return PriceEval(bull=0, bear=0,
                         reasons=[Reason("insufficient_data", "데이터가 부족합니다(신규 상장 등)", "na")],
                         indicators={})

    close = df["Close"]
    mas = ind.moving_averages(close)
    ma20 = mas.get(f"MA{config.MA_PERIODS[0]}")
    ma60 = mas.get(f"MA{config.MA_PERIODS[1]}")
    rsi_s = ind.rsi(close)
    macd_df = ind.macd(close)
    bb = ind.bollinger(close)
    obv_s = ind.obv(df)
    vol = ind.volume_signal(df)

    bull = 0
    bear = 0

    # 60일선 기울기 (크로스보다 기울기 중시)
    slope60 = ind.ma_slope(ma60) if ma60 is not None else 0.0
    if slope60 > 0:
        bull += config.BULL_WEIGHTS["ma60_slope_up"]
        reasons.append(Reason("ma60_slope_up", "60일선 기울기 우상향", "bull", f"기울기 {slope60:+.2%}"))
    elif slope60 < 0:
        bear += config.BEAR_WEIGHTS["ma60_slope_down"]
        reasons.append(Reason("ma60_slope_down", "60일선 기울기 하락(꺾임)", "bear", f"기울기 {slope60:+.2%}"))
    else:
        reasons.append(Reason("ma60_slope_flat", "60일선 기울기 평평 → 경고 구간", "neutral"))

    # 20일선 위 종가 + 거래량
    above_ma20 = bool(ma20 is not None and close.iloc[-1] > ma20.iloc[-1])
    if above_ma20 and vol["surge"]:
        bull += config.BULL_WEIGHTS["above_ma20_with_volume"]
        reasons.append(Reason("above_ma20_with_volume", "20일선 위 종가 + 거래량 급증", "bull",
                              f"거래량 {vol['volume_ratio']:.0%} vs 20일 평균"))
    elif above_ma20:
        reasons.append(Reason("above_ma20", "20일선 위 종가(거래량 평범)", "bull",
                              f"거래량 {vol['volume_ratio']:.0%}"))

    # 20일선 이탈 후 회복 실패
    if ma20 is not None and len(df) >= 2:
        broke = close.iloc[-2] < ma20.iloc[-2]
        not_recovered = close.iloc[-1] < ma20.iloc[-1]
        if broke and not_recovered:
            bear += config.BEAR_WEIGHTS["break_ma20"]
            reasons.append(Reason("break_ma20", "20일선 이탈 후 회복 실패", "bear"))

    # 골든/데드크로스
    if ma20 is not None and ma60 is not None:
        cross = ind.detect_cross(ma20, ma60)
        if cross == "golden":
            bull += config.BULL_WEIGHTS["golden_cross"]
            reasons.append(Reason("golden_cross", "골든크로스(20>60) 발생", "bull"))
        elif cross == "dead":
            bear += config.BEAR_WEIGHTS["dead_cross"]
            reasons.append(Reason("dead_cross", "데드크로스(20<60) 발생", "bear"))

    # 다이버전스 (RSI/OBV)
    if ind.bearish_divergence(close, rsi_s):
        bear += config.BEAR_WEIGHTS["bearish_divergence"]
        reasons.append(Reason("rsi_divergence", "약세 다이버전스(가격 신고가 vs RSI 고점 낮아짐)", "bear"))
    elif ind.bearish_divergence(close, obv_s):
        bear += config.BEAR_WEIGHTS["bearish_divergence"]
        reasons.append(Reason("obv_divergence", "약세 다이버전스(가격 신고가 vs OBV 못 따라옴)", "bear"))
    elif ind.bullish_divergence(close, rsi_s):
        bull += config.BULL_WEIGHTS["ma60_slope_up"] // 2
        reasons.append(Reason("bullish_divergence", "강세 다이버전스(가격 신저가 vs RSI 저점 높아짐)", "bull"))

    indicators = {
        "close": close,
        "ma": mas,
        "rsi": rsi_s,
        "macd": macd_df,
        "bollinger": bb,
        "envelope": ind.envelope(close),
        "obv": obv_s,
        "volume": df["Volume"],
        "squeeze": ind.is_squeeze(bb),
        "volume_label": vol["label"],
    }
    return PriceEval(bull=bull, bear=bear, reasons=reasons, indicators=indicators)


def _market_context(stock: data_mod.StockData, period: str):
    """VIX/SOX/외국인 수급 등 '최신 시점' 시장맥락 근거. (bull, bear, reasons) 반환."""
    reasons: list[Reason] = []
    bull = 0
    bear = 0

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
            bull += config.BULL_WEIGHTS["vix_calm"]
            reasons.append(Reason("vix_calm", f"VIX 안정({vix_now:.1f}, 하락 중)", "bull"))
        elif vix_now >= config.VIX_FEAR:
            reasons.append(Reason("vix_fear", f"VIX 공포 구간({vix_now:.1f})", "bear",
                                  "역발상 매수 타이밍이 나올 수 있는 구간"))
    else:
        reasons.append(Reason("vix_na", "VIX 데이터 없음", "na"))

    if not sox_df.empty and len(sox_df) >= config.MA_PERIODS[0]:
        sox_close = sox_df["Close"]
        sox_ma20 = sox_close.rolling(config.MA_PERIODS[0]).mean().iloc[-1]
        sox_change = sox_close.pct_change().iloc[-1]
        sox_drop = bool(sox_change <= -0.03)
        if sox_close.iloc[-1] > sox_ma20:
            bull += config.BULL_WEIGHTS["sox_above_ma20"]
            reasons.append(Reason("sox_above_ma20", "SOX(반도체) 20일선 위", "bull"))
        else:
            reasons.append(Reason("sox_below_ma20", "SOX(반도체) 20일선 아래", "bear"))
    else:
        reasons.append(Reason("sox_na", "SOX 데이터 없음", "na"))

    if vix_spike and sox_drop:
        bear += config.BEAR_WEIGHTS["vix_spike_sox_drop"]
        reasons.append(Reason("vix_spike_sox_drop", "VIX 급등 + SOX 급락 동반", "bear"))

    if stock.is_korean:
        netbuy = data_mod.get_foreign_netbuy(stock.ticker)
        if netbuy is not None and len(netbuy) >= 5:
            if (netbuy.tail(3) > 0).all():
                bull += config.BULL_WEIGHTS["foreign_net_buy"]
                reasons.append(Reason("foreign_net_buy", "외국인 3일 연속 순매수", "bull"))
            elif (netbuy.tail(5) < 0).all():
                bear += config.BEAR_WEIGHTS["foreign_net_sell"]
                reasons.append(Reason("foreign_net_sell", "외국인 5일 연속 순매도", "bear"))
        else:
            if not data_mod.pykrx_installed():
                msg = "외국인 수급: pykrx 미설치 (pip install pykrx)"
            else:
                msg = "외국인 수급 조회 실패 (KRX 네트워크·해외 서버 차단·휴장 가능)"
            reasons.append(Reason("foreign_na", msg, "na"))

    return bull, bear, reasons


def analyze(stock: data_mod.StockData, period: str = config.DEFAULT_PERIOD) -> TrendResult:
    """단일 종목 최신 판정: 가격 코어 + 시장맥락."""
    core = evaluate_price(stock.ohlcv)
    if not core.indicators:  # 데이터 부족
        return TrendResult(verdict="중립", score=0, reasons=core.reasons, indicators={})

    m_bull, m_bear, m_reasons = _market_context(stock, period)

    bull_score = core.bull + m_bull
    bear_score = core.bear + m_bear
    score = int(_clamp(bull_score - bear_score, -100, 100))
    verdict = score_to_verdict(score)

    reasons = list(core.reasons) + m_reasons
    reasons.append(Reason("volume_quadrant", core.indicators["volume_label"], "neutral"))

    indicators = dict(core.indicators)
    indicators.update({"bull_score": bull_score, "bear_score": bear_score})
    return TrendResult(verdict=verdict, score=score, reasons=reasons, indicators=indicators)


def quick_verdict(df: pd.DataFrame) -> tuple[str, int]:
    """가격 코어만으로 (verdict, score). 워치리스트/백테스트용 경량 판정."""
    core = evaluate_price(df)
    if not core.indicators:
        return "중립", 0
    score = int(_clamp(core.bull - core.bear, -100, 100))
    return score_to_verdict(score), score

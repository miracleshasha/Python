"""매크로(시장 레짐) 지표.

전체 시장 환경을 점수화한다: KOSPI 추세, VIX(공포), SOX(반도체 선행).
개별 종목이 아닌 '시장 공통' 요인이라, 예측 랭킹에서 전체 점수를 위/아래로 기울인다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import config
from core import data as data_mod


@dataclass
class MacroRegime:
    score: float                    # -100(위험회피) ~ +100(위험선호)
    label: str
    factors: list = field(default_factory=list)   # (설명, 방향) 리스트

    @property
    def z(self) -> float:
        """블렌드용 정규화 값(-1 ~ +1)."""
        return max(-1.0, min(1.0, self.score / 100.0))


def _ma_trend(close, short=20, long=60) -> int:
    """종가가 단기>장기 MA & 우상향이면 +1, 반대면 -1, 애매하면 0."""
    if close is None or len(close) < long:
        return 0
    ma_s = close.rolling(short).mean().iloc[-1]
    ma_l = close.rolling(long).mean().iloc[-1]
    last = close.iloc[-1]
    if last > ma_s > ma_l:
        return 1
    if last < ma_s < ma_l:
        return -1
    return 0


def market_regime(period: str = "1y") -> MacroRegime:
    """KOSPI/VIX/SOX로 시장 레짐 산출. 데이터 없으면 중립(0)."""
    score = 0.0
    factors = []

    # KOSPI 추세 (^KS11)
    kospi = data_mod.get_market_index("^KS11", period)
    if not kospi.empty:
        t = _ma_trend(kospi["Close"])
        score += t * 40
        factors.append(("KOSPI 이동평균 추세", "bull" if t > 0 else "bear" if t < 0 else "neutral"))
    else:
        factors.append(("KOSPI 데이터 없음", "na"))

    # VIX (공포지수) — 낮으면 위험선호(+), 높으면 위험회피(-)
    vix = data_mod.get_market_index(config.MARKET_INDEX_VIX, period)
    if not vix.empty:
        v = float(vix["Close"].iloc[-1])
        if v <= config.VIX_NORMAL:
            score += 30; factors.append((f"VIX 안정({v:.0f})", "bull"))
        elif v >= config.VIX_FEAR:
            score -= 30; factors.append((f"VIX 공포({v:.0f})", "bear"))
        else:
            factors.append((f"VIX 보통({v:.0f})", "neutral"))
    else:
        factors.append(("VIX 데이터 없음", "na"))

    # SOX (반도체 선행) — 국내 증시 민감
    sox = data_mod.get_market_index(config.MARKET_INDEX_SOX, period)
    if not sox.empty:
        t = _ma_trend(sox["Close"])
        score += t * 30
        factors.append(("SOX(반도체) 추세", "bull" if t > 0 else "bear" if t < 0 else "neutral"))
    else:
        factors.append(("SOX 데이터 없음", "na"))

    score = max(-100.0, min(100.0, score))
    label = "위험선호(강세)" if score >= 30 else "위험회피(약세)" if score <= -30 else "중립"
    return MacroRegime(score=score, label=label, factors=factors)

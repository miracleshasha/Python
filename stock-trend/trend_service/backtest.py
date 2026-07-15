"""백테스트: 과거 시점 판정의 사후 성과를 집계한다.

각 거래일 t에서 그 시점까지의 데이터만으로(evaluate_price, look-ahead 없음) 판정하고,
이후 horizon 거래일 뒤 수익률을 기록한다. 상승/하락 신호별 적중률·평균 수익률을 낸다.

주의: 지표는 확률을 높이는 도구이며, 백테스트 성과가 미래를 보장하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

import config
from trend_service.engine import MIN_BARS, evaluate_price, score_to_verdict


@dataclass
class SignalStats:
    count: int = 0
    wins: int = 0                 # 방향이 맞은 횟수
    avg_return: float = 0.0       # 평균 forward 수익률
    hit_rate: float = 0.0         # 적중률


@dataclass
class BacktestResult:
    horizon: int
    bull: SignalStats = field(default_factory=SignalStats)
    bear: SignalStats = field(default_factory=SignalStats)
    total_signals: int = 0
    trades: pd.DataFrame = field(default_factory=pd.DataFrame)  # 개별 신호 기록


def _score(df_slice: pd.DataFrame) -> int:
    core = evaluate_price(df_slice)
    if not core.indicators:
        return 0
    return int(max(-100, min(100, core.bull - core.bear)))


def run(df: pd.DataFrame, horizon: int = None, step: int = 1) -> BacktestResult:
    """OHLCV 전체 구간을 백테스트한다.

    horizon: 신호 발생 후 성과를 측정할 거래일 수(보유기간).
    step: 몇 거래일마다 판정할지(1이면 매일). 큰 데이터에서 속도 조절용.
    """
    horizon = horizon or config.BACKTEST_HORIZON
    close = df["Close"].reset_index(drop=True)
    n = len(df)
    records = []

    # t는 판정 시점, t+horizon 종가로 수익률 측정
    start = MIN_BARS
    for t in range(start, n - horizon, step):
        score = _score(df.iloc[: t + 1])
        verdict = score_to_verdict(score)
        if verdict == "중립":
            continue
        entry = close.iloc[t]
        exit_ = close.iloc[t + horizon]
        if entry == 0:
            continue
        fwd = (exit_ - entry) / entry
        records.append({"idx": t, "verdict": verdict, "score": score, "fwd_return": fwd})

    trades = pd.DataFrame(records)
    result = BacktestResult(horizon=horizon, trades=trades, total_signals=len(trades))
    if trades.empty:
        return result

    for verdict, stats in (("상승", result.bull), ("하락", result.bear)):
        sub = trades[trades["verdict"] == verdict]
        if sub.empty:
            continue
        stats.count = len(sub)
        stats.avg_return = float(sub["fwd_return"].mean())
        # 방향 적중: 상승 신호는 forward>0, 하락 신호는 forward<0
        if verdict == "상승":
            stats.wins = int((sub["fwd_return"] > 0).sum())
        else:
            stats.wins = int((sub["fwd_return"] < 0).sum())
        stats.hit_rate = stats.wins / stats.count if stats.count else 0.0

    return result

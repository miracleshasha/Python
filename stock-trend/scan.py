"""워치리스트 자동 스캔 CLI.

저장된 관심종목을 순회하며 각 종목의 현재 추세를 판정하고,
진입(상승)/청산(하락) 신호가 잡히면 알림을 남긴다.
cron 등으로 정기 실행하면 조건 충족 시 자동으로 알림 로그가 쌓인다.

사용:
    python scan.py                 # 워치리스트 전체 스캔
    python scan.py 005930 AAPL     # 인자로 준 티커만 스캔
    python scan.py --all           # 상승/하락뿐 아니라 중립도 출력

정기 실행 예(매 평일 오후 4시):
    0 16 * * 1-5  cd /path/to/stock-trend && python scan.py >> data/scan.out 2>&1
"""
from __future__ import annotations

import sys

from core import data as data_mod
from core import watchlist
from core.notify import notify
from trend_service.engine import analyze


def scan(tickers: list[str], period: str = "1y", include_neutral: bool = False) -> int:
    """티커들을 스캔해 신호를 알린다. 알림 건수를 반환."""
    if not tickers:
        notify("워치리스트가 비어 있습니다. app.py에서 종목을 추가하세요.")
        return 0

    alerts = 0
    for raw in tickers:
        stock = data_mod.get_stock_data(raw, period)
        if stock.ohlcv.empty:
            notify(f"⚠️  {raw}: 데이터를 가져오지 못했습니다(티커 확인).")
            continue
        result = analyze(stock, period)
        if result.verdict == "상승":
            notify(f"🟢 매수 신호  {stock.ticker}  score {result.score:+d}")
            alerts += 1
        elif result.verdict == "하락":
            notify(f"🔴 매도/청산 신호  {stock.ticker}  score {result.score:+d}")
            alerts += 1
        elif include_neutral:
            notify(f"⚪ 중립  {stock.ticker}  score {result.score:+d}")
    return alerts


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    include_neutral = "--all" in argv
    tickers = args if args else watchlist.load()
    count = scan(tickers, include_neutral=include_neutral)
    notify(f"스캔 완료: {len(tickers)}종목 중 신호 {count}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

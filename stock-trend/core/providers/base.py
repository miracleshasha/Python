"""데이터 provider 인터페이스.

시장별 구현(krx.py, 향후 us.py)이 따르는 계약. 스크리너/유니버스/펀더멘털 계층은
이 인터페이스에만 의존한다.
"""
from __future__ import annotations

from typing import Protocol

import pandas as pd


class QuantDataProvider(Protocol):
    """퀀트에 필요한 시장 데이터 조회 계약."""

    def index_constituents(self, index_code: str) -> list[str]:
        """지수(예: 코스피200) 구성종목 티커 리스트. 실패 시 빈 리스트."""
        ...

    def fundamental_snapshot(self, market: str, date: str | None = None) -> pd.DataFrame:
        """시장 전체 펀더멘털 횡단면. index=티커, cols≈[PER,PBR,EPS,BPS,DIV]. 실패 시 빈 DF."""
        ...

    def marketcap_snapshot(self, market: str, date: str | None = None) -> pd.DataFrame:
        """시장 전체 시가총액 횡단면. index=티커, col=[시가총액]. 실패 시 빈 DF."""
        ...

    def close_snapshot(self, market: str, date: str | None = None) -> pd.Series:
        """시장 전체 종가 횡단면. index=티커, value=종가. 실패 시 빈 Series."""
        ...

    def ticker_name(self, ticker: str) -> str | None:
        """종목명. 실패 시 None."""
        ...

"""금융위원회 주식시세정보 API 클라이언트 (data.go.kr).

국내 종목의 일별 시세(OHLCV)와 종목명을 공공데이터포털의
GetStockSecuritiesInfoService/getStockPriceInfo 오퍼레이션으로 조회한다.

인증키는 **환경변수 `DATA_GO_KR_API_KEY`** 로 주입한다(코드/레포에 하드코딩 금지).
    export DATA_GO_KR_API_KEY="발급받은_일반_인증키"

네트워크가 없거나 키가 없으면 빈 결과를 반환해 상위(data.py)가 yfinance로 폴백한다.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

ENDPOINT = (
    "https://apis.data.go.kr/1160100/service/"
    "GetStockSecuritiesInfoService/getStockPriceInfo"
)
API_KEY_ENV = "DATA_GO_KR_API_KEY"

# 응답 필드 → 표준 OHLCV 컬럼
_FIELD_MAP = {"mkp": "Open", "hipr": "High", "lopr": "Low", "clpr": "Close", "trqu": "Volume"}


def api_key() -> Optional[str]:
    key = os.environ.get(API_KEY_ENV)
    return key.strip() if key else None


def _code(ticker: str) -> Optional[str]:
    """티커에서 6자리 단축코드 추출(예: '005930.KS' -> '005930')."""
    m = re.match(r"^(\d{6})", ticker)
    return m.group(1) if m else None


def _period_to_dates(period: str) -> tuple[str, str]:
    """'6mo'/'1y'/'2y' → (beginBasDt, endBasDt) YYYYMMDD."""
    days = {"6mo": 190, "1y": 380, "2y": 760}.get(period, 380)
    end = datetime.now()
    begin = end - timedelta(days=days)
    return begin.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def _request(code: str, params: dict) -> list[dict]:
    """API 호출 후 item 리스트 반환. 실패 시 빈 리스트."""
    if requests is None:
        return []
    key = api_key()
    if not key:
        return []
    base = {
        "serviceKey": key,
        "resultType": "json",
        "numOfRows": 1000,
        "pageNo": 1,
        "likeSrtnCd": code,
    }
    base.update(params)
    try:
        resp = requests.get(ENDPOINT, params=base, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return []
    return _extract_items(data)


def _extract_items(data: dict) -> list[dict]:
    """응답 JSON에서 item 리스트를 안전하게 뽑아낸다."""
    try:
        body = data["response"]["body"]
        items = body.get("items")
        if not items:
            return []
        item = items.get("item") if isinstance(items, dict) else items
        if item is None:
            return []
        return item if isinstance(item, list) else [item]
    except (KeyError, TypeError, AttributeError):
        return []


def _total_count(data: dict) -> int:
    try:
        return int(data["response"]["body"]["totalCount"])
    except (KeyError, TypeError, ValueError):
        return 0


def recent_business_days(n: int = 8) -> list[str]:
    """최근 영업일 후보(YYYYMMDD). 주말 제외, n일치. 데이터 미공개일 대비 여러 날 시도용."""
    days, d = [], datetime.now()
    while len(days) < n:
        if d.weekday() < 5:  # 월~금
            days.append(d.strftime("%Y%m%d"))
        d -= timedelta(days=1)
    return days


def _request_all(params: dict, page_size: int = 1000, max_pages: int = 6) -> list[dict]:
    """likeSrtnCd 없이 임의 조건으로 전체 페이지를 순회 조회. 실패 시 빈 리스트."""
    if requests is None or not api_key():
        return []
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        base = {"serviceKey": api_key(), "resultType": "json",
                "numOfRows": page_size, "pageNo": page}
        base.update(params)
        try:
            resp = requests.get(ENDPOINT, params=base, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            break
        items = _extract_items(data)
        if not items:
            break
        out.extend(items)
        if len(out) >= _total_count(data) or len(items) < page_size:
            break
    return out


def parse_listing(items: list[dict], market_cls: Optional[str] = None) -> pd.DataFrame:
    """getStockPriceInfo item → 상장목록 DataFrame[ticker,name,market,mktcap]."""
    rows = []
    for it in items:
        code = str(it.get("srtnCd", "")).zfill(6)
        name = it.get("itmsNm")
        if not code.isdigit() or not name:
            continue
        try:
            mktcap = float(it.get("mrktTotAmt")) if it.get("mrktTotAmt") else float("nan")
        except (ValueError, TypeError):
            mktcap = float("nan")
        rows.append({"ticker": code, "name": str(name),
                     "market": it.get("mrktCtg") or market_cls or "", "mktcap": mktcap})
    if not rows:
        return pd.DataFrame(columns=["ticker", "name", "market", "mktcap"])
    return pd.DataFrame(rows).drop_duplicates("ticker").reset_index(drop=True)


def fetch_listing(market_cls: str = "KOSPI") -> pd.DataFrame:
    """시장(KOSPI/KOSDAQ) 전체 상장목록을 금융위 API로 조회(전역 접근). 실패 시 빈 DF.

    최근 영업일부터 데이터가 나오는 날을 찾아 페이지 순회 조회한다.
    """
    for bas in recent_business_days(8):
        items = _request_all({"basDt": bas, "mrktCls": market_cls})
        df = parse_listing(items, market_cls)
        if not df.empty:
            return df
    return pd.DataFrame(columns=["ticker", "name", "market", "mktcap"])


def parse_ohlcv(items: list[dict], code: str) -> pd.DataFrame:
    """item 리스트 → OHLCV DataFrame(yfinance와 동일한 형태). 코드 정확일치만 사용."""
    rows = []
    for it in items:
        if str(it.get("srtnCd", "")).zfill(6) != code:
            continue  # likeSrtnCd는 부분일치이므로 정확한 종목만 필터
        try:
            rows.append({
                "Date": pd.to_datetime(str(it["basDt"]), format="%Y%m%d"),
                "Open": float(it["mkp"]),
                "High": float(it["hipr"]),
                "Low": float(it["lopr"]),
                "Close": float(it["clpr"]),
                "Volume": float(it["trqu"]),
            })
        except (KeyError, ValueError, TypeError):
            continue
    if not rows:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    df = pd.DataFrame(rows).drop_duplicates("Date").set_index("Date").sort_index()
    return df


def fetch_ohlcv(ticker: str, period: str = "1y") -> pd.DataFrame:
    """국내 종목 일별 OHLCV 조회. 실패/키없음 시 빈 DataFrame."""
    code = _code(ticker)
    if not code:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    begin, end = _period_to_dates(period)
    items = _request(code, {"beginBasDt": begin, "endBasDt": end})
    return parse_ohlcv(items, code)


def fetch_name(ticker: str) -> Optional[str]:
    """국내 종목명(itmsNm) 조회. 실패 시 None."""
    code = _code(ticker)
    if not code:
        return None
    items = _request(code, {"numOfRows": 1})
    for it in items:
        if str(it.get("srtnCd", "")).zfill(6) == code and it.get("itmsNm"):
            return str(it["itmsNm"])
    return None

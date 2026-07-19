"""금융위 API 대량 상장목록 파싱 테스트 (합성 JSON, 네트워크 불필요)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import krx_api  # noqa: E402


SAMPLE_ITEMS = [
    {"srtnCd": "005930", "itmsNm": "삼성전자", "mrktCtg": "KOSPI", "mrktTotAmt": "400000000000000"},
    {"srtnCd": "000660", "itmsNm": "SK하이닉스", "mrktCtg": "KOSPI", "mrktTotAmt": "100000000000000"},
    {"srtnCd": "005935", "itmsNm": "삼성전자우", "mrktCtg": "KOSPI", "mrktTotAmt": "50000000000000"},
    {"srtnCd": "", "itmsNm": None, "mrktCtg": "KOSPI"},   # 무효 → 스킵
]


def test_parse_listing_maps_and_filters():
    df = krx_api.parse_listing(SAMPLE_ITEMS, "KOSPI")
    assert list(df.columns) == ["ticker", "name", "market", "mktcap"]
    assert len(df) == 3                    # 무효 1건 제외
    assert set(df["ticker"]) == {"005930", "000660", "005935"}
    row = df[df["ticker"] == "005930"].iloc[0]
    assert row["name"] == "삼성전자"
    assert row["mktcap"] == 4e14


def test_parse_listing_marketcap_sort_for_universe():
    df = krx_api.parse_listing(SAMPLE_ITEMS, "KOSPI")
    top1 = df.sort_values("mktcap", ascending=False).iloc[0]
    assert top1["ticker"] == "005930"      # 시총 1위


def test_extract_items_and_total():
    data = {"response": {"body": {"totalCount": 2,
            "items": {"item": [{"srtnCd": "005930"}, {"srtnCd": "000660"}]}}}}
    assert len(krx_api._extract_items(data)) == 2
    assert krx_api._total_count(data) == 2


def test_recent_business_days_are_weekdays():
    from datetime import datetime
    days = krx_api.recent_business_days(8)
    assert len(days) == 8
    for d in days:
        assert datetime.strptime(d, "%Y%m%d").weekday() < 5


def test_fetch_listing_empty_without_key(monkeypatch):
    monkeypatch.delenv("DATA_GO_KR_API_KEY", raising=False)
    assert krx_api.fetch_listing("KOSPI").empty

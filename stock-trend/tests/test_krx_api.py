"""금융위원회 주식시세정보 API 파싱 테스트 (네트워크 없이, 샘플 응답)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from trend_service import krx_api  # noqa: E402


# getStockPriceInfo 응답의 대표 구조(축약)
SAMPLE = {
    "response": {
        "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
        "body": {
            "numOfRows": 3, "pageNo": 1, "totalCount": 3,
            "items": {"item": [
                {"basDt": "20240710", "srtnCd": "005930", "itmsNm": "삼성전자",
                 "mkp": "80000", "hipr": "81000", "lopr": "79500", "clpr": "80500", "trqu": "12000000"},
                {"basDt": "20240711", "srtnCd": "005930", "itmsNm": "삼성전자",
                 "mkp": "80500", "hipr": "82000", "lopr": "80000", "clpr": "81800", "trqu": "15000000"},
                # 부분일치로 섞여 들어온 다른 종목 → 필터되어야 함
                {"basDt": "20240711", "srtnCd": "0059301", "itmsNm": "기타",
                 "mkp": "1", "hipr": "1", "lopr": "1", "clpr": "1", "trqu": "1"},
            ]},
        },
    }
}


def test_extract_items():
    items = krx_api._extract_items(SAMPLE)
    assert len(items) == 3


def test_extract_items_empty():
    assert krx_api._extract_items({"response": {"body": {"items": ""}}}) == []
    assert krx_api._extract_items({}) == []


def test_parse_ohlcv_filters_and_maps():
    items = krx_api._extract_items(SAMPLE)
    df = krx_api.parse_ohlcv(items, "005930")
    # 정확일치 2행만(0059301 제외), 날짜 오름차순
    assert len(df) == 2
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert df["Close"].iloc[-1] == 81800.0
    assert df["Open"].iloc[0] == 80000.0
    assert df.index.is_monotonic_increasing


def test_parse_ohlcv_single_item_dict():
    # item이 단일 dict로 오는 경우도 리스트로 처리
    single = {"response": {"body": {"items": {"item":
              {"basDt": "20240710", "srtnCd": "005930", "itmsNm": "삼성전자",
               "mkp": "1", "hipr": "2", "lopr": "1", "clpr": "2", "trqu": "10"}}}}}
    items = krx_api._extract_items(single)
    assert len(items) == 1
    df = krx_api.parse_ohlcv(items, "005930")
    assert len(df) == 1


def test_no_key_returns_empty(monkeypatch):
    monkeypatch.delenv(krx_api.API_KEY_ENV, raising=False)
    assert krx_api.fetch_ohlcv("005930.KS").empty
    assert krx_api.fetch_name("005930.KS") is None


def test_code_extraction():
    assert krx_api._code("005930.KS") == "005930"
    assert krx_api._code("AAPL") is None

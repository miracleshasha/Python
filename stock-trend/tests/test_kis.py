"""KIS provider 응답 파싱 테스트 (합성 JSON, 네트워크 불필요)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.providers import kis  # noqa: E402


def test_available_false_without_keys(monkeypatch):
    monkeypatch.delenv("KIS_APP_KEY", raising=False)
    monkeypatch.delenv("KIS_APP_SECRET", raising=False)
    assert kis.available() is False


def test_parse_price():
    data = {"output": {"stck_prpr": "71,500", "prdy_vrss": "1,200",
                       "prdy_ctrt": "1.71", "acml_vol": "12345678",
                       "bstp_kor_isnm": "전기전자"}}
    p = kis.parse_price(data)
    assert p["price"] == 71500.0
    assert p["change_pct"] == 1.71
    assert p["volume"] == 12345678.0


def test_parse_price_empty():
    assert kis.parse_price({}) == {}
    assert kis.parse_price({"output": {}}) == {}


def test_parse_minutes():
    data = {"output2": [
        {"stck_bsop_date": "20260728", "stck_cntg_hour": "090000",
         "stck_oprc": "71000", "stck_hgpr": "71500", "stck_lwpr": "70900",
         "stck_prpr": "71400", "cntg_vol": "5000"},
        {"stck_bsop_date": "20260728", "stck_cntg_hour": "090100",
         "stck_oprc": "71400", "stck_hgpr": "71800", "stck_lwpr": "71300",
         "stck_prpr": "71700", "cntg_vol": "6000"},
    ]}
    df = kis.parse_minutes(data)
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 2
    assert df.index.is_monotonic_increasing
    assert df["Close"].iloc[-1] == 71700.0


def test_parse_foreign_institution():
    data = {"output": [
        {"mksc_shrn_iscd": "005930", "frgn_ntby_tr_pbmn": "120000000000",
         "orgn_ntby_tr_pbmn": "30000000000"},
        {"mksc_shrn_iscd": "000660", "frgn_ntby_tr_pbmn": "-50000000000",
         "orgn_ntby_tr_pbmn": "10000000000"},
    ]}
    df = kis.parse_foreign_institution(data)
    assert set(df.columns) == {"외국인", "기관"}
    assert df.loc["005930", "외국인"] == 1.2e11
    assert df.loc["000660", "외국인"] == -5e10


def test_parse_foreign_institution_empty():
    assert kis.parse_foreign_institution({}).empty


def test_calls_return_empty_without_keys(monkeypatch):
    monkeypatch.delenv("KIS_APP_KEY", raising=False)
    monkeypatch.delenv("KIS_APP_SECRET", raising=False)
    assert kis.current_price("005930") == {}
    assert kis.minute_candles("005930").empty
    assert kis.foreign_institution_total("KOSPI").empty

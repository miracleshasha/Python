"""워치리스트 저장/관리 테스트 (임시 디렉터리)."""
import importlib
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _fresh_module(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCK_TREND_DATA", str(tmp_path))
    from trend_service import watchlist
    importlib.reload(watchlist)
    return watchlist


def test_empty_by_default(tmp_path, monkeypatch):
    wl = _fresh_module(tmp_path, monkeypatch)
    assert wl.load() == []


def test_add_and_load(tmp_path, monkeypatch):
    wl = _fresh_module(tmp_path, monkeypatch)
    wl.add("AAPL")
    wl.add("005930")
    assert set(wl.load()) == {"AAPL", "005930"}


def test_add_dedup_by_canonical(tmp_path, monkeypatch):
    wl = _fresh_module(tmp_path, monkeypatch)
    wl.add("005930")
    wl.add("005930.KS")   # 정규화하면 동일 → 중복 무시
    wl.add("aapl")
    wl.add("AAPL")        # 대소문자 동일 → 중복 무시
    assert len(wl.load()) == 2


def test_remove(tmp_path, monkeypatch):
    wl = _fresh_module(tmp_path, monkeypatch)
    wl.add("AAPL")
    wl.add("NVDA")
    wl.remove("aapl")     # 정규화 매칭 제거
    assert wl.load() == ["NVDA"]


def test_add_empty_ignored(tmp_path, monkeypatch):
    wl = _fresh_module(tmp_path, monkeypatch)
    wl.add("   ")
    assert wl.load() == []

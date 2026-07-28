"""한국투자증권(KIS) Open API provider.

실시간/분봉 시세와 투자자 수급(외국인·기관)을 공식 REST API로 조회한다. 전역 접근이라
클라우드에서도 동작한다. 인증정보는 환경변수/Secrets로만 주입(레포 커밋 금지):
    KIS_APP_KEY, KIS_APP_SECRET, (선택) KIS_ENV=real|vps(모의)

네트워크/키 없음/오류 시 빈 결과로 폴백한다. 조회(시세·수급)만 사용하며 주문 기능은 없다.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

import config

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


# --------------------------------------------------------------------------
# 설정/인증
# --------------------------------------------------------------------------
def _key() -> Optional[str]:
    v = os.environ.get(config.KIS_APP_KEY_ENV)
    return v.strip() if v else None


def _secret() -> Optional[str]:
    v = os.environ.get(config.KIS_APP_SECRET_ENV)
    return v.strip() if v else None


def _base() -> str:
    env = (os.environ.get(config.KIS_ENV_ENV) or "real").strip().lower()
    return config.KIS_BASE.get(env, config.KIS_BASE["real"])


def available() -> bool:
    """KIS 사용 가능 여부(키·시크릿·requests 존재)."""
    return bool(requests and _key() and _secret())


def _token_cache_path() -> Path:
    base = os.environ.get("STOCK_TREND_DATA")
    root = Path(base) if base else Path(__file__).resolve().parent.parent.parent / "data"
    return root / "cache" / "kis_token.json"


def _access_token() -> Optional[str]:
    """액세스 토큰(24h) 발급/캐시. 실패 시 None."""
    if not available():
        return None
    path = _token_cache_path()
    # 캐시된 유효 토큰 재사용
    try:
        if path.exists():
            cached = json.loads(path.read_text())
            if cached.get("token") and cached.get("expire", 0) > time.time() + 60:
                return cached["token"]
    except Exception:
        pass
    # 신규 발급
    try:
        resp = requests.post(
            f"{_base()}/oauth2/tokenP",
            json={"grant_type": "client_credentials", "appkey": _key(), "appsecret": _secret()},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        if not token:
            return None
        expire = time.time() + int(data.get("expires_in", 86400))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"token": token, "expire": expire}))
        except Exception:
            pass
        return token
    except Exception:
        return None


def _get(path: str, tr_id: str, params: dict) -> dict:
    """공통 GET 호출. 실패 시 빈 dict."""
    token = _access_token()
    if not token:
        return {}
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": _key(),
        "appsecret": _secret(),
        "tr_id": tr_id,
        "custtype": "P",
    }
    try:
        resp = requests.get(f"{_base()}{path}", headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


def _code(ticker: str) -> str:
    return str(ticker)[:6]


def _f(v) -> float:
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return float("nan")


# --------------------------------------------------------------------------
# 현재가
# --------------------------------------------------------------------------
def parse_price(data: dict) -> dict:
    out = data.get("output") or {}
    if not out:
        return {}
    return {
        "price": _f(out.get("stck_prpr")),
        "change": _f(out.get("prdy_vrss")),
        "change_pct": _f(out.get("prdy_ctrt")),
        "volume": _f(out.get("acml_vol")),
        "name": out.get("bstp_kor_isnm") or None,
    }


def current_price(ticker: str) -> dict:
    """현재가·전일대비·등락률. 실패 시 {}."""
    data = _get("/uapi/domestic-stock/v1/quotations/inquire-price", "FHKST01010100",
                {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": _code(ticker)})
    return parse_price(data)


# --------------------------------------------------------------------------
# 분봉
# --------------------------------------------------------------------------
def parse_minutes(data: dict) -> pd.DataFrame:
    rows = data.get("output2") or []
    recs = []
    for it in rows:
        try:
            d = str(it.get("stck_bsop_date", ""))
            t = str(it.get("stck_cntg_hour", "")).zfill(6)
            ts = pd.to_datetime(d + t, format="%Y%m%d%H%M%S", errors="coerce")
            recs.append({
                "Datetime": ts,
                "Open": _f(it.get("stck_oprc")), "High": _f(it.get("stck_hgpr")),
                "Low": _f(it.get("stck_lwpr")), "Close": _f(it.get("stck_prpr")),
                "Volume": _f(it.get("cntg_vol")),
            })
        except Exception:
            continue
    if not recs:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    df = pd.DataFrame(recs).dropna(subset=["Datetime"]).set_index("Datetime").sort_index()
    return df


def minute_candles(ticker: str) -> pd.DataFrame:
    """당일 분봉 OHLCV. 실패 시 빈 DataFrame."""
    now = datetime.now().strftime("%H%M%S")
    data = _get("/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice", "FHKST03010200",
                {"FID_ETC_CLS_CODE": "", "FID_COND_MRKT_DIV_CODE": "J",
                 "FID_INPUT_ISCD": _code(ticker), "FID_INPUT_HOUR_1": now,
                 "FID_PW_DATA_INCU_YN": "Y"})
    return parse_minutes(data)


# --------------------------------------------------------------------------
# 수급 (외국인·기관 매매종목 가집계, 횡단면)
# --------------------------------------------------------------------------
def parse_foreign_institution(data: dict) -> pd.DataFrame:
    rows = data.get("output") or []
    recs = []
    for it in rows:
        code = str(it.get("mksc_shrn_iscd") or it.get("stck_shrn_iscd") or "").zfill(6)
        if not code.isdigit():
            continue
        frgn = _f(it.get("frgn_ntby_tr_pbmn") or it.get("frgn_ntby_qty"))
        orgn = _f(it.get("orgn_ntby_tr_pbmn") or it.get("orgn_ntby_qty"))
        recs.append({"ticker": code, "외국인": frgn, "기관": orgn})
    if not recs:
        return pd.DataFrame(columns=["외국인", "기관"])
    return pd.DataFrame(recs).drop_duplicates("ticker").set_index("ticker")


def foreign_institution_total(market: str = "전체") -> pd.DataFrame:
    """기관·외국인 순매수(금액) 종목 가집계 횡단면. 실패 시 빈 DF.

    반환 DataFrame: index=티커, cols=[외국인, 기관].
    """
    iscd = {"전체": "0000", "KOSPI": "0001", "KOSDAQ": "1001"}.get(market, "0000")
    data = _get("/uapi/domestic-stock/v1/quotations/foreign-institution-total", "FHPTJ04400000",
                {"FID_COND_MRKT_DIV_CODE": "V", "FID_COND_SCR_DIV_CODE": "16449",
                 "FID_INPUT_ISCD": iscd, "FID_DIV_CLS_CODE": "1",
                 "FID_RANK_SORT_CLS_CODE": "0", "FID_ETC_CLS_CODE": "0"})
    return parse_foreign_institution(data)

"""퀀트 스크리너 페이지 (Streamlit).

코스피200·코스닥150 유니버스에서 밸류·퀄리티·모멘텀 팩터로 종목을 랭킹한다.
데이터는 pykrx(KRX) — 국내 네트워크가 필요하며, 해외/클라우드에선 조회가 막힐 수 있다.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config
import ui
from core import universe as universe_mod
from core import fundamentals as fundamentals_mod
from core import watchlist
from core.env import sync_secrets
from core.providers import krx
from quant_service import screener

sync_secrets()

st.set_page_config(page_title="퀀트 스크리너", page_icon="🧮", layout="wide")
ui.inject_css()

st.title("🧮 퀀트 스크리너")
st.caption("코스피200 · 코스닥150 유니버스에서 밸류·퀄리티·모멘텀 팩터로 종목을 랭킹합니다.")
st.warning(
    "⚠️ 투자 자문이 아닙니다. 팩터 점수는 과거·현재 지표에 기반한 상대 순위일 뿐이며, "
    "미래 수익을 보장하지 않습니다. 실제 투자 판단과 책임은 본인에게 있습니다."
)

# --- 입력 ---
c1, c2 = st.columns([2, 3])
with c1:
    indices = st.multiselect(
        "유니버스", list(config.QUANT_UNIVERSE_INDICES),
        default=list(config.QUANT_UNIVERSE_INDICES),
    )
    top_n = st.slider("상위 종목 수", 5, 50, config.QUANT_TOP_N, step=5)
    exclude_pref = st.checkbox("우선주 제외", value=config.QUANT_EXCLUDE_PREFERRED)
with c2:
    st.markdown("**팩터 가중치** (합계 자동 정규화)")
    w_val = st.slider("밸류 (저PER·저PBR·고배당)", 0, 100, config.QUANT_FACTOR_WEIGHTS["value"], step=5)
    w_qual = st.slider("퀄리티 (ROE)", 0, 100, config.QUANT_FACTOR_WEIGHTS["quality"], step=5)
    w_mom = st.slider(f"모멘텀 ({config.QUANT_MOMENTUM_MONTHS}개월 수익률)", 0, 100,
                      config.QUANT_FACTOR_WEIGHTS["momentum"], step=5)

run = st.button("🔎 스크리닝 실행", type="primary")

if run:
    if not indices:
        st.error("유니버스를 하나 이상 선택하세요.")
        st.stop()
    weights = {"value": w_val, "quality": w_qual, "momentum": w_mom}

    with st.spinner("유니버스·펀더멘털 조회 중... (최초 1회는 다소 걸릴 수 있습니다)"):
        uni = universe_mod.get_universe(indices)
        snapshot = fundamentals_mod.get_snapshot(uni) if not uni.empty else pd.DataFrame()

    if uni.empty or snapshot.empty:
        st.error(
            "데이터를 불러오지 못했습니다. pykrx는 KRX(국내)를 조회하므로 "
            "**해외/클라우드 서버에서는 차단**될 수 있습니다. 국내 네트워크(로컬 등)에서 실행하거나, "
            "휴장·일시 오류가 아닌지 확인하세요."
        )
        st.stop()

    result = screener.screen(snapshot, weights=weights, top_n=top_n, exclude_preferred=exclude_pref)
    if result.empty:
        st.warning("조건에 맞는 종목이 없습니다.")
        st.stop()

    # 상위 종목 종목명 보강(상위 N만 → 호출 최소화)
    result["종목명"] = [krx.ticker_name(t) or "-" for t in result["ticker"]]

    st.success(f"유니버스 {len(uni)}종목 중 상위 {len(result)}종목")

    # 표시용 표
    show = result.rename(columns={
        "rank": "순위", "ticker": "티커", "market": "시장", "score": "종합점수",
        "value_z": "밸류z", "quality_z": "퀄리티z", "momentum_z": "모멘텀z",
        "MOM": f"{config.QUANT_MOMENTUM_MONTHS}M수익률",
    })
    cols = ["순위", "티커", "종목명", "시장", "종합점수", "밸류z", "퀄리티z", "모멘텀z",
            "PER", "PBR", "DIV", "ROE", f"{config.QUANT_MOMENTUM_MONTHS}M수익률"]
    cols = [c for c in cols if c in show.columns]
    fmt = {"종합점수": "{:.2f}", "밸류z": "{:.2f}", "퀄리티z": "{:.2f}", "모멘텀z": "{:.2f}",
           "PER": "{:.1f}", "PBR": "{:.2f}", "DIV": "{:.2f}", "ROE": "{:.1%}",
           f"{config.QUANT_MOMENTUM_MONTHS}M수익률": "{:.1%}"}
    fmt = {k: v for k, v in fmt.items() if k in show.columns}
    st.dataframe(show[cols].style.format(fmt), use_container_width=True, hide_index=True)

    # 팩터 기여(상위 10) 시각화
    st.subheader("상위 종목 팩터 기여")
    top10 = result.head(10).set_index("ticker")[["value_z", "quality_z", "momentum_z"]]
    top10.columns = ["밸류", "퀄리티", "모멘텀"]
    st.bar_chart(top10)

    # 관심종목 일괄 추가
    st.subheader("관심종목 추가")
    picks = st.multiselect("추가할 종목", list(result["ticker"]))
    if st.button("⭐ 선택 종목 관심등록") and picks:
        for t in picks:
            watchlist.add(t)
        st.toast(f"{len(picks)}종목 추가됨")
else:
    st.info("유니버스·가중치를 정하고 **스크리닝 실행**을 눌러주세요. 기본값: 밸류 40 / 퀄리티 30 / 모멘텀 30")

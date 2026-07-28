"""추세 판정 페이지 (Streamlit 멀티페이지).

구성:
- 사이드바: 종목 검색 + ⭐ 관심종목(즐겨찾기) 상시 노출 + 데이터소스 상태
- 메인: 단일 분석 / 워치리스트 / 백테스트 탭 (카드형 레이아웃)
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config
import ui
from core import charts
from core import data as data_mod
from core import krx_api
from core import watchlist
from core.env import sync_secrets
from core.providers import kis
from trend_service import backtest as bt
from trend_service.engine import analyze

sync_secrets()  # Streamlit Secrets → 환경변수 브리지

st.set_page_config(page_title="종목 추세 판단", page_icon="📈", layout="wide")
ui.inject_css()

PERIOD_MAP = {"6개월": "6mo", "1년": "1y", "2년": "2y"}

# 세션 상태 초기화
st.session_state.setdefault("ticker", "005930")
st.session_state.setdefault("period", "1y")
st.session_state.setdefault("analysis", None)   # (stock, result) 튜플 캐시


# --------------------------------------------------------------------------
# 분석 실행 (세션 상태에 결과 저장 → 다른 버튼 클릭에도 화면 유지)
# --------------------------------------------------------------------------
def run_analysis(ticker: str, period: str):
    ticker = ticker.strip()
    if not ticker:
        return
    st.session_state.ticker = ticker
    st.session_state.period = period
    with st.spinner(f"'{ticker}' 데이터를 분석 중..."):
        stock = data_mod.get_stock_data(ticker, period)
    if stock.ohlcv.empty:
        st.session_state.analysis = ("error", ticker)
    else:
        st.session_state.analysis = (stock, analyze(stock, period))


def _load_favorite(ticker: str):
    """사이드바 관심종목 클릭 → 해당 종목 분석."""
    run_analysis(ticker, st.session_state.period)


# --------------------------------------------------------------------------
# 사이드바: 검색 + 관심종목(즐겨찾기) 상시 노출
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 📈 종목 추세 판단")
    st.caption("이동평균·거래량/OBV·RSI/MACD·볼린저·엔벨로프·VIX/SOX 종합 판정")

    st.markdown("### 🔎 종목 검색")
    # 종목명으로 검색 → 티커 자동 입력 후 즉시 분석 (선택이 바뀔 때만)
    searched = ui.ticker_search_box("trend_name_search")
    if searched and searched != st.session_state.get("last_searched"):
        st.session_state.last_searched = searched
        st.session_state.ticker = searched
        run_analysis(searched, st.session_state.period)
    s_ticker = st.text_input("티커", value=st.session_state.ticker,
                             placeholder="한국 6자리(005930) / 미국 심볼(AAPL)", key="search_input")
    s_period = st.selectbox("기간", list(PERIOD_MAP),
                            index=list(PERIOD_MAP.values()).index(st.session_state.period))
    b1, b2 = st.columns(2)
    if b1.button("분석", type="primary", use_container_width=True):
        run_analysis(s_ticker, PERIOD_MAP[s_period])
    if b2.button("⭐ 관심등록", use_container_width=True):
        if s_ticker.strip():
            watchlist.add(s_ticker)
            st.toast(f"'{s_ticker.strip()}' 관심종목 추가")

    st.divider()
    st.markdown("### ⭐ 관심종목")
    favs = watchlist.load()
    if not favs:
        st.caption("아직 없습니다. 위 **⭐ 관심등록**으로 추가하세요.")
    else:
        for raw in favs:
            fc1, fc2 = st.columns([4, 1])
            if fc1.button(f"📊 {raw}", key=f"fav_{raw}", use_container_width=True):
                _load_favorite(raw)
            if fc2.button("🗑", key=f"favdel_{raw}", use_container_width=True):
                watchlist.remove(raw)
                st.rerun()

    st.divider()
    if krx_api.api_key():
        st.caption("🟢 국내: 금융위 API · 미국: yfinance")
    else:
        st.caption("⚪ 국내: yfinance 폴백 · 미국: yfinance\n\n`DATA_GO_KR_API_KEY` 설정 시 금융위 API 사용")


# --------------------------------------------------------------------------
# 메인 헤더 + 안내
# --------------------------------------------------------------------------
st.markdown(
    """
    <div style="border:2px solid #dc2626; background:rgba(220,38,38,0.06);
                border-radius:10px; padding:12px 18px; margin-bottom:10px;">
      <span style="color:#dc2626; font-size:1.25rem; font-weight:800;">
        📌 한국 종목은 6자리 코드(예: 005930), 미국 종목은 심볼(예: AAPL)
      </span>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("⚠️ 투자 자문이 아닙니다. 기술적 지표는 확률을 높이는 참고 도구이며, 손실 책임은 본인에게 있습니다.")

tab_single, tab_watch, tab_back = st.tabs(["🔍 단일 분석", "⭐ 워치리스트", "🧪 백테스트"])


# --------------------------------------------------------------------------
# 탭 1: 단일 분석 (세션 상태의 분석 결과를 렌더)
# --------------------------------------------------------------------------
def render_realtime(stock):
    """KIS 실시간 현재가 + 당일 분봉 (KIS 키 있을 때, 국내 종목)."""
    if not (stock.is_korean and kis.available()):
        return
    ui.section_title("실시간 시세 · 분봉 (KIS)")
    price = kis.current_price(stock.ticker)
    if price:
        c1, c2, c3 = st.columns(3)
        c1.metric("현재가", f"{price.get('price', float('nan')):,.0f}원",
                  f"{price.get('change_pct', float('nan')):+.2f}%")
        c2.metric("전일대비", f"{price.get('change', float('nan')):,.0f}")
        c3.metric("누적거래량", f"{price.get('volume', float('nan')):,.0f}")
    mdf = kis.minute_candles(stock.ticker)
    if mdf.empty:
        st.caption("분봉 데이터를 불러오지 못했습니다(장 시작 전·휴장·조회 한도 등).")
    else:
        st.plotly_chart(charts.minute_chart(mdf.tail(config.KIS_MINUTE_COUNT), "당일 분봉"),
                        use_container_width=True)


def render_investor_flows(stock):
    ui.section_title("투자자별 수급 (외국인·기관·개인)")
    if not stock.is_korean:
        st.caption("해외 종목은 투자자별 수급 데이터를 제공하지 않습니다.")
        return
    flows = data_mod.get_investor_flows(stock.ticker, days=20)
    if flows is None or flows.empty:
        if not data_mod.pykrx_installed():
            st.caption("수급 데이터: `pykrx` 미설치 — `pip install pykrx` 후 이용하세요.")
        else:
            st.caption("수급 데이터를 불러오지 못했습니다. pykrx는 KRX(국내)를 조회하므로, "
                       "**해외/클라우드 서버에서는 KRX가 차단**되어 실패할 수 있습니다. "
                       "휴장·해당 종목 데이터 없음도 원인일 수 있습니다.")
        return
    totals = flows.sum()
    cols = st.columns(len(totals))
    for col, (name, val) in zip(cols, totals.items()):
        col.metric(f"{name} 순매수(20일)", f"{val/1e8:,.1f}억")
    st.bar_chart(flows)
    with st.expander("일자별 수급 표 보기"):
        st.dataframe(flows.iloc[::-1], use_container_width=True)


with tab_single:
    analysis = st.session_state.analysis
    if analysis is None:
        st.info("👈 왼쪽 사이드바에서 종목을 검색하거나 관심종목을 눌러 분석을 시작하세요.")
    elif analysis[0] == "error":
        st.error(f"'{analysis[1]}' 데이터를 가져오지 못했습니다. 티커를 확인하세요. "
                 "(한국=6자리 숫자, 미국=심볼)")
    else:
        stock, result = analysis
        col_star, _ = st.columns([1, 4])
        with col_star:
            if st.button("⭐ 이 종목 관심등록", use_container_width=True):
                watchlist.add(stock.raw_input)
                st.toast(f"'{stock.raw_input}' 관심종목 추가")

        ui.verdict_hero(stock, result)
        ui.kpi_row(result)

        ui.section_title("판정 근거")
        ui.reason_columns(result.reasons)

        ui.section_title("차트")
        st.caption("캔들 + 이동평균(20/60/120) + 볼린저밴드(점선) + 엔벨로프(파선, ±6%) · 하단 거래량/RSI/MACD")
        st.plotly_chart(charts.build_chart(stock.ohlcv, result, title=stock.display_name),
                        use_container_width=True)

        render_realtime(stock)
        render_investor_flows(stock)


# --------------------------------------------------------------------------
# 탭 2: 워치리스트 대시보드
# --------------------------------------------------------------------------
with tab_watch:
    ui.section_title("관심종목 대시보드")
    period2 = PERIOD_MAP[st.selectbox("기간", list(PERIOD_MAP), index=1, key="wl_period")]

    items = watchlist.load()
    if not items:
        st.info("저장된 관심종목이 없습니다. 사이드바에서 **⭐ 관심등록**으로 추가하세요.")
    else:
        if st.button("🔄 전체 판정 새로고침", type="primary"):
            rows = []
            prog = st.progress(0.0)
            for i, raw in enumerate(items):
                stock = data_mod.get_stock_data(raw, period2)
                if stock.ohlcv.empty:
                    rows.append({"티커": raw, "종목명": "-", "판정": "데이터없음", "스코어": None})
                else:
                    res = analyze(stock, period2)
                    rows.append({"티커": stock.ticker, "종목명": stock.name or "-",
                                 "판정": res.verdict, "스코어": res.score})
                prog.progress((i + 1) / len(items))
            st.session_state["wl_rows"] = rows
        if st.session_state.get("wl_rows"):
            df = pd.DataFrame(st.session_state["wl_rows"])
            st.dataframe(df, use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------
# 탭 3: 백테스트
# --------------------------------------------------------------------------
with tab_back:
    ui.section_title("판정 성과 백테스트")
    st.caption("과거 각 시점에서 그 시점까지의 데이터만으로 판정하고(look-ahead 없음), "
               "이후 보유기간 수익률을 집계합니다. 가격 기반 코어 신호만 사용.")

    bc1, bc2, bc3, bc4 = st.columns([2, 2, 2, 1])
    with bc1:
        bt_ticker = st.text_input("티커", value="AAPL", key="bt_ticker")
    with bc2:
        bt_period = PERIOD_MAP[st.selectbox("기간", list(PERIOD_MAP), index=2, key="bt_period")]
    with bc3:
        horizon = st.number_input("보유기간(거래일)", min_value=5, max_value=120,
                                  value=config.BACKTEST_HORIZON, step=5)
    with bc4:
        st.write("")
        st.write("")
        run_bt = st.button("실행", type="primary", use_container_width=True)

    if run_bt and bt_ticker.strip():
        with st.spinner("백테스트 중..."):
            stock = data_mod.get_stock_data(bt_ticker, bt_period)
            if stock.ohlcv.empty:
                st.error(f"'{bt_ticker}' 데이터를 가져오지 못했습니다.")
            else:
                result = bt.run(stock.ohlcv, horizon=int(horizon))
                if result.total_signals == 0:
                    st.warning("신호가 없었습니다. 기간을 늘려보세요.")
                else:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("총 신호 수", result.total_signals)
                    m2.metric("🟢 상승신호 적중률", f"{result.bull.hit_rate:.0%}",
                              help=f"{result.bull.wins}/{result.bull.count} · 평균 {result.bull.avg_return:+.2%}")
                    m3.metric("🔴 하락신호 적중률", f"{result.bear.hit_rate:.0%}",
                              help=f"{result.bear.wins}/{result.bear.count} · 평균 {result.bear.avg_return:+.2%}")
                    st.dataframe(pd.DataFrame([
                        {"신호": "상승", "표본": result.bull.count, "적중률": f"{result.bull.hit_rate:.0%}",
                         "평균수익률": f"{result.bull.avg_return:+.2%}"},
                        {"신호": "하락", "표본": result.bear.count, "적중률": f"{result.bear.hit_rate:.0%}",
                         "평균수익률": f"{result.bear.avg_return:+.2%}"},
                    ]), use_container_width=True, hide_index=True)
                    st.caption("⚠️ 과거 성과가 미래 수익을 보장하지 않습니다. 표본 수가 작으면 신뢰도가 낮습니다.")

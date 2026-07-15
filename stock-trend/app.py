"""종목 추세 판단 웹 서비스 (Streamlit UI).

실행: streamlit run app.py

탭 구성:
- 단일 분석: 티커 하나의 추세를 근거·차트와 함께 판정
- 워치리스트: 관심종목을 저장하고 전 종목 판정을 한눈에
- 백테스트: 과거 시점 판정의 사후 성과(적중률·평균 수익률) 검증
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import config
from trend_service import backtest as bt
from trend_service import charts
from trend_service import data as data_mod
from trend_service import watchlist
from trend_service.engine import analyze, quick_verdict

st.set_page_config(page_title="종목 추세 판단", page_icon="📈", layout="wide")

VERDICT_STYLE = {
    "상승": ("🟢", "#16a34a"),
    "하락": ("🔴", "#dc2626"),
    "중립": ("⚪", "#6b7280"),
}
DIRECTION_ICON = {"bull": "✅", "bear": "❌", "neutral": "▫️", "na": "➖"}

PERIOD_MAP = {"6개월": "6mo", "1년": "1y", "2년": "2y"}

st.title("📈 종목 추세 판단")
st.caption(
    "이동평균 기울기·거래량/OBV·RSI/MACD·볼린저밴드·엔벨로프·VIX/SOX 시장심리를 규칙으로 종합해 "
    "추세를 판정합니다."
)

# 티커 입력 안내 — 눈에 잘 띄게 빨간색·큰 폰트로 강조 (요청 5)
st.markdown(
    """
    <div style="border:2px solid #dc2626; background:rgba(220,38,38,0.06);
                border-radius:10px; padding:14px 18px; margin:8px 0 4px 0;">
      <span style="color:#dc2626; font-size:1.35rem; font-weight:800;">
        📌 한국 종목은 6자리 코드(예: 005930), 미국 종목은 심볼(예: AAPL)
      </span>
    </div>
    """,
    unsafe_allow_html=True,
)
st.warning(
    "⚠️ 이 서비스는 **투자 자문이 아닙니다.** 기술적 지표는 확률을 높이는 참고 도구이며, "
    "어떤 조합도 100% 적중하지 않습니다. 실제 투자 판단과 손실 책임은 본인에게 있습니다."
)

tab_single, tab_watch, tab_back = st.tabs(["🔍 단일 분석", "⭐ 워치리스트", "🧪 백테스트"])


# --------------------------------------------------------------------------
# 탭 1: 단일 분석
# --------------------------------------------------------------------------
def render_result(stock, result):
    icon, color = VERDICT_STYLE.get(result.verdict, ("⚪", "#6b7280"))

    # 종목명 헤더 (요청 1)
    st.markdown(f"### {stock.display_name}")

    # 최종 결과 강조 박스 (요청 3) — 큰 폰트·색상으로 돋보이게
    st.markdown(
        f"""
        <div style="border:3px solid {color}; border-radius:14px;
                    padding:18px 22px; margin:6px 0 14px 0;
                    background:{color}12; text-align:center;">
          <div style="font-size:1.1rem; color:#6b7280; font-weight:600;">최종 결과</div>
          <div style="font-size:2.6rem; font-weight:900; color:{color}; line-height:1.2;">
            {icon} {result.verdict}
          </div>
          <div style="font-size:1.1rem; color:{color}; font-weight:700;">
            종합 스코어 {result.score:+d}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.progress(int((result.score + 100) / 2))
    st.caption(
        f"조회 티커: `{stock.ticker}` · 상승근거 {result.indicators.get('bull_score', 0)} / "
        f"하락근거 {result.indicators.get('bear_score', 0)}"
    )
    if result.indicators.get("squeeze"):
        st.info("🔎 볼린저밴드 스퀴즈(변동성 수축) → 곧 큰 방향성이 나올 수 있습니다. 방향은 거래량으로 확인.")

    st.subheader("판정 근거")
    for r in result.reasons:
        st.write(f"{DIRECTION_ICON.get(r.direction, '▫️')} **{r.label}**"
                 + (f" — {r.detail}" if r.detail else ""))

    st.subheader("차트")
    st.caption("가격 패널: 캔들 + 이동평균(20/60/120) + 볼린저밴드(점선) + 엔벨로프(파선, ±6%)")
    st.plotly_chart(charts.build_chart(stock.ohlcv, result, title=stock.ticker),
                    use_container_width=True)

    render_investor_flows(stock)


def render_investor_flows(stock):
    """외국인·기관·개인 수급 표 + 막대차트 (요청 4). 국내 종목·pykrx 있을 때만."""
    st.subheader("투자자별 수급 (외국인·기관·개인)")
    if not stock.is_korean:
        st.caption("해외 종목은 투자자별 수급 데이터를 제공하지 않습니다.")
        return
    flows = data_mod.get_investor_flows(stock.ticker, days=20)
    if flows is None or flows.empty:
        st.caption("수급 데이터를 불러오지 못했습니다. (pykrx 설치 또는 네트워크 필요 — `pip install pykrx`)")
        return
    # 최근 순매수 합계 요약 + 일자별 막대차트
    totals = flows.sum()
    cols = st.columns(len(totals))
    for col, (name, val) in zip(cols, totals.items()):
        col.metric(f"{name} 순매수(최근 20일)", f"{val/1e8:,.1f}억")
    st.bar_chart(flows)
    with st.expander("일자별 수급 표 보기"):
        st.dataframe(flows.iloc[::-1], use_container_width=True)


with tab_single:
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1:
        ticker = st.text_input("종목 티커", value="005930", placeholder="예: 005930, 000660.KQ, AAPL")
    with c2:
        period_label = st.selectbox("기간", list(PERIOD_MAP), index=1)
    with c3:
        st.write("")
        st.write("")
        run = st.button("분석", type="primary", use_container_width=True)

    add_col, _ = st.columns([1, 4])
    with add_col:
        if st.button("⭐ 워치리스트에 추가", use_container_width=True) and ticker.strip():
            watchlist.add(ticker)
            st.success(f"'{ticker}' 추가됨")

    if run and ticker.strip():
        period = PERIOD_MAP[period_label]
        with st.spinner("데이터를 불러오는 중..."):
            stock = data_mod.get_stock_data(ticker, period)
        if stock.ohlcv.empty:
            st.error(f"'{ticker}' 데이터를 가져오지 못했습니다. 티커를 확인하세요.")
        else:
            render_result(stock, analyze(stock, period))
    else:
        st.info("티커를 입력하고 **분석**을 눌러주세요.")


# --------------------------------------------------------------------------
# 탭 2: 워치리스트
# --------------------------------------------------------------------------
with tab_watch:
    st.subheader("관심종목 대시보드")
    period2 = PERIOD_MAP[st.selectbox("기간", list(PERIOD_MAP), index=1, key="wl_period")]

    ac1, ac2 = st.columns([3, 1])
    with ac1:
        new_t = st.text_input("종목 추가", placeholder="예: AAPL", key="wl_add")
    with ac2:
        st.write("")
        st.write("")
        if st.button("추가", use_container_width=True) and new_t.strip():
            watchlist.add(new_t)
            st.rerun()

    items = watchlist.load()
    if not items:
        st.info("저장된 관심종목이 없습니다. 위에서 추가하거나, 단일 분석 탭에서 ⭐로 추가하세요.")
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
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.write("**목록 관리**")
        for raw in items:
            rc1, rc2 = st.columns([4, 1])
            rc1.write(f"• {raw}")
            if rc2.button("삭제", key=f"del_{raw}"):
                watchlist.remove(raw)
                st.rerun()


# --------------------------------------------------------------------------
# 탭 3: 백테스트
# --------------------------------------------------------------------------
with tab_back:
    st.subheader("판정 성과 백테스트")
    st.caption("과거 각 시점에서 그 시점까지의 데이터만으로 판정하고, 이후 보유기간 수익률을 집계합니다. "
               "(look-ahead 없음) 가격 기반 코어 신호만 사용합니다.")

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
                    st.write(pd.DataFrame([
                        {"신호": "상승", "표본": result.bull.count, "적중률": f"{result.bull.hit_rate:.0%}",
                         "평균수익률": f"{result.bull.avg_return:+.2%}"},
                        {"신호": "하락", "표본": result.bear.count, "적중률": f"{result.bear.hit_rate:.0%}",
                         "평균수익률": f"{result.bear.avg_return:+.2%}"},
                    ]))
                    st.caption("⚠️ 과거 성과가 미래 수익을 보장하지 않습니다. 표본 수가 작으면 신뢰도가 낮습니다.")

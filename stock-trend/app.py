"""종목 추세 판단 웹 서비스 (Streamlit UI).

실행: streamlit run app.py

티커를 입력하면 이동평균·거래량·RSI/MACD·시장심리를 종합해
상승/하락/중립을 근거와 함께 보여준다.
"""
from __future__ import annotations

import streamlit as st

import config
from trend_service import data as data_mod
from trend_service import charts
from trend_service.engine import analyze

st.set_page_config(page_title="종목 추세 판단", page_icon="📈", layout="wide")

VERDICT_STYLE = {
    "상승": ("🟢", "#16a34a"),
    "하락": ("🔴", "#dc2626"),
    "중립": ("⚪", "#6b7280"),
}
DIRECTION_ICON = {"bull": "✅", "bear": "❌", "neutral": "▫️", "na": "➖"}

st.title("📈 종목 추세 판단")
st.caption(
    "이동평균 기울기·거래량/OBV·RSI/MACD·볼린저밴드·VIX/SOX 시장심리를 규칙으로 종합해 "
    "추세를 판정합니다. 한국 종목은 6자리 코드(예: 005930), 미국 종목은 심볼(예: AAPL)."
)

# 면책 배너
st.warning(
    "⚠️ 이 서비스는 **투자 자문이 아닙니다.** 기술적 지표는 확률을 높이는 참고 도구이며, "
    "어떤 조합도 100% 적중하지 않습니다. 실제 투자 판단과 손실 책임은 본인에게 있습니다."
)

# 입력
col1, col2, col3 = st.columns([3, 2, 1])
with col1:
    ticker = st.text_input("종목 티커", value="005930", placeholder="예: 005930, 000660.KQ, AAPL")
with col2:
    period_label = st.selectbox("기간", ["6개월", "1년", "2년"], index=1)
    period = {"6개월": "6mo", "1년": "1y", "2년": "2y"}[period_label]
with col3:
    st.write("")
    st.write("")
    run = st.button("분석", type="primary", use_container_width=True)

if run and ticker.strip():
    with st.spinner("데이터를 불러오는 중..."):
        stock = data_mod.get_stock_data(ticker, period)

    if stock.ohlcv.empty:
        st.error(
            f"'{ticker}' 데이터를 가져오지 못했습니다. 티커가 올바른지 확인하세요. "
            "(한국 종목은 6자리 숫자, 미국 종목은 심볼)"
        )
    else:
        result = analyze(stock, period)

        icon, color = VERDICT_STYLE.get(result.verdict, ("⚪", "#6b7280"))
        st.markdown("---")
        top1, top2 = st.columns([1, 2])
        with top1:
            st.markdown(
                f"<h2 style='color:{color}'>{icon} {result.verdict}</h2>",
                unsafe_allow_html=True,
            )
            st.metric("종합 스코어", f"{result.score:+d}", help="-100(강한 하락) ~ +100(강한 상승)")
        with top2:
            # -100~100 → 0~100 게이지
            st.progress(int((result.score + 100) / 2))
            st.caption(f"조회 티커: `{stock.ticker}` · 상승근거 {result.indicators.get('bull_score', 0)} / "
                       f"하락근거 {result.indicators.get('bear_score', 0)}")
            if result.indicators.get("squeeze"):
                st.info("🔎 볼린저밴드 스퀴즈(변동성 수축) 상태 → 곧 큰 방향성이 나올 수 있습니다. 방향은 거래량으로 확인.")

        # 근거
        st.subheader("판정 근거")
        for r in result.reasons:
            st.write(f"{DIRECTION_ICON.get(r.direction, '▫️')} **{r.label}**"
                     + (f" — {r.detail}" if r.detail else ""))

        # 차트
        st.subheader("차트")
        fig = charts.build_chart(stock.ohlcv, result, title=stock.ticker)
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("이 판정은 어떻게 계산되나요?"):
            st.markdown(
                "- **상승 근거**: 60일선 기울기 우상향, 20일선 위 종가+거래량 급증, "
                "골든크로스, SOX 20일선 위, VIX 안정, 외국인 순매수(국내)\n"
                "- **하락 근거**: 60일선 꺾임, 20일선 이탈 후 회복 실패, 데드크로스, "
                "약세 다이버전스(RSI/OBV), VIX 급등+SOX 급락, 외국인 순매도(국내)\n"
                "- 각 항목에 가중치를 두고 (상승근거 − 하락근거)를 -100~+100 스코어로 환산합니다.\n"
                "- 임계값(±25)으로 상승/중립/하락을 구분합니다. `config.py`에서 조정 가능합니다."
            )
else:
    st.info("티커를 입력하고 **분석**을 눌러주세요.")

"""상승/하락 예측 랭킹 페이지 (코스피200 한정).

추세판정 점수 + 투자자 수급(외국인·기관·개인) + 매크로(시장 레짐)를 블렌드해
상승 가능성 top N / 하락 가능성 top N을 뽑는다.
"""
from __future__ import annotations

import streamlit as st

import config
import ui
from core.env import sync_secrets
from prediction_service import ranking

sync_secrets()

st.set_page_config(page_title="상승/하락 예측", page_icon="📊", layout="wide")
ui.inject_css()


def _billify(v):
    return f"{v/1e8:,.0f}억" if v == v else "-"   # NaN이면 "-"


def _render_table(df):
    show_cols = [c for c in ["순위", "종목명", "ticker", "예측점수", "추세점수",
                             "외국인", "기관", "개인"] if c in df.columns]
    view = df[show_cols].rename(columns={"ticker": "티커"})
    fmt = {"예측점수": "{:.2f}", "추세점수": "{:.0f}"}
    for c in ("외국인", "기관", "개인"):
        if c in view.columns:
            fmt[c] = _billify
    st.dataframe(view.style.format(fmt), use_container_width=True, hide_index=True)

st.title("📊 상승 / 하락 예측 랭킹")

# 코스피200 한정 명시 (요청 2)
st.markdown(
    """
    <div style="border:2px solid #2563eb; background:rgba(37,99,235,0.06);
                border-radius:10px; padding:12px 18px; margin:6px 0 12px 0;">
      <span style="color:#2563eb; font-size:1.2rem; font-weight:800;">
        📌 대상: <u>코스피200 한정</u> (국내 대형주 200종목)
      </span>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("추세판정 점수 + 수급(외국인·기관·개인) + 매크로(KOSPI·VIX·SOX)를 블렌드해 랭킹합니다.")
st.warning(
    "⚠️ 투자 자문이 아닙니다. '가능성'은 지표 기반 상대 순위일 뿐이며 미래를 보장하지 않습니다. "
    "실제 투자 판단과 책임은 본인에게 있습니다."
)

# 가중치/설정
c1, c2, c3, c4 = st.columns(4)
w_trend = c1.slider("추세 가중치", 0, 100, config.PREDICT_WEIGHTS["trend"], step=5)
w_flow = c2.slider("수급 가중치", 0, 100, config.PREDICT_WEIGHTS["flow"], step=5)
w_macro = c3.slider("매크로 가중치", 0, 100, config.PREDICT_WEIGHTS["macro"], step=5)
top_n = c4.slider("상·하위 종목 수", 5, 30, config.PREDICT_TOP_N, step=5)

run = st.button("🚀 예측 랭킹 생성", type="primary")
st.caption("※ 코스피200 전 종목의 시세를 조회하므로 **최초 1회는 수 분** 걸릴 수 있습니다(이후 당일 캐시).")

if run:
    weights = {"trend": w_trend, "flow": w_flow, "macro": w_macro}
    bar = st.progress(0.0, text="코스피200 종목 추세 분석 중...")

    def _progress(frac):
        bar.progress(min(1.0, frac), text=f"코스피200 종목 추세 분석 중... {frac:.0%}")

    result = ranking.build_ranking(weights=weights, top_n=top_n, progress=_progress)
    bar.empty()

    # 매크로 레짐
    if result.macro is not None:
        m = result.macro
        color = "#16a34a" if m.score >= 30 else "#dc2626" if m.score <= -30 else "#6b7280"
        st.markdown(
            f"<div class='st-card' style='border-left:6px solid {color};'>"
            f"<h4>🌐 매크로 시장 레짐</h4>"
            f"<div style='font-size:1.4rem;font-weight:800;color:{color};'>{m.label} "
            f"<span style='font-size:1rem;'>(스코어 {m.score:+.0f})</span></div>"
            f"<div style='color:#6b7280;margin-top:4px;'>"
            + " · ".join(f"{name}" for name, _ in m.factors) + "</div></div>",
            unsafe_allow_html=True,
        )

    if result.error and (result.up is None or result.up.empty):
        st.error(
            f"{result.error}\n\n"
            "예측 랭킹은 pykrx(KRX)·yfinance 데이터를 사용합니다. **해외/클라우드 서버에서는 "
            "KRX가 차단**될 수 있어, 국내 네트워크(로컬 등)에서 실행해야 실데이터가 나옵니다."
        )
    elif not result.up.empty:
        st.success(f"코스피200 {result.universe_size}종목 분석 완료")
        col_up, col_down = st.columns(2)
        with col_up:
            st.markdown("### 🟢 상승 가능성 TOP")
            _render_table(result.up)
        with col_down:
            st.markdown("### 🔴 하락 가능성 TOP")
            _render_table(result.down)
else:
    st.info("가중치를 정하고 **예측 랭킹 생성**을 눌러주세요. 기본: 추세 50 / 수급 30 / 매크로 20")

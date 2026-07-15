"""UI 컴포넌트 & 스타일 헬퍼 (Streamlit 전용).

로직(trend_service)과 분리된 표현 계층. 카드/칩/KPI 등 재사용 렌더 함수와
전역 CSS 주입을 담당한다. 주식/인사이트 사이트 느낌의 카드형 레이아웃을 만든다.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

VERDICT = {
    "상승": {"icon": "🟢", "color": "#16a34a", "bg": "rgba(22,163,74,0.10)", "label": "상승 추세"},
    "하락": {"icon": "🔴", "color": "#dc2626", "bg": "rgba(220,38,38,0.10)", "label": "하락 추세"},
    "중립": {"icon": "⚪", "color": "#6b7280", "bg": "rgba(107,114,128,0.10)", "label": "중립 / 관망"},
}
DIRECTION = {
    "bull": {"color": "#16a34a", "chip": "rgba(22,163,74,0.12)", "icon": "▲"},
    "bear": {"color": "#dc2626", "chip": "rgba(220,38,38,0.12)", "icon": "▼"},
    "neutral": {"color": "#6b7280", "chip": "rgba(107,114,128,0.12)", "icon": "•"},
    "na": {"color": "#9ca3af", "chip": "rgba(156,163,175,0.10)", "icon": "–"},
}


def inject_css() -> None:
    """전역 스타일. 카드·칩·타이포·여백을 정돈한다."""
    st.markdown(
        """
        <style>
          .block-container { padding-top: 1.6rem; max-width: 1200px; }
          /* 카드 */
          .st-card {
            border: 1px solid rgba(128,128,128,0.20);
            border-radius: 14px; padding: 18px 20px; background: rgba(250,250,252,0.6);
            box-shadow: 0 1px 3px rgba(0,0,0,0.04); margin-bottom: 14px;
          }
          .st-card h4 { margin: 0 0 10px 0; font-size: 0.95rem; color: #6b7280;
                        font-weight: 700; letter-spacing: .2px; }
          /* 칩 */
          .chip { display:inline-block; padding:6px 12px; margin:4px 6px 4px 0;
                  border-radius: 999px; font-size: 0.9rem; font-weight: 600; line-height:1.35; }
          .chip small { opacity:.75; font-weight:500; }
          /* 섹션 타이틀 */
          .sec-title { font-size:1.15rem; font-weight:800; margin: 6px 0 10px 0; }
          /* 사이드바 관심종목 버튼 폭 맞춤 */
          section[data-testid="stSidebar"] .stButton button { text-align:left; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _fmt_price(value: float, is_korean: bool) -> str:
    if is_korean:
        return f"{value:,.0f}원"
    return f"${value:,.2f}"


def price_change(ohlcv: pd.DataFrame) -> tuple[float, float]:
    """(현재가, 전일대비 등락률%) 반환."""
    close = ohlcv["Close"]
    if len(close) < 2:
        return float(close.iloc[-1]), 0.0
    last, prev = float(close.iloc[-1]), float(close.iloc[-2])
    pct = (last - prev) / prev * 100 if prev else 0.0
    return last, pct


def verdict_hero(stock, result) -> None:
    """헤더 카드: 종목명 + 현재가 + 등락 + 대형 판정 뱃지."""
    v = VERDICT.get(result.verdict, VERDICT["중립"])
    last, pct = price_change(stock.ohlcv)
    up = pct >= 0
    chg_color = "#16a34a" if up else "#dc2626"
    arrow = "▲" if up else "▼"
    name = stock.name or ""
    st.markdown(
        f"""
        <div class="st-card" style="border-left:6px solid {v['color']}; background:{v['bg']};
             display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px;">
          <div>
            <div style="font-size:1.7rem; font-weight:900; line-height:1.1;">{name}
              <span style="font-size:1.0rem; color:#6b7280; font-weight:600;">{stock.ticker}</span>
            </div>
            <div style="margin-top:6px;">
              <span style="font-size:1.9rem; font-weight:800;">{_fmt_price(last, stock.is_korean)}</span>
              <span style="font-size:1.1rem; font-weight:700; color:{chg_color}; margin-left:10px;">
                {arrow} {abs(pct):.2f}%
              </span>
            </div>
          </div>
          <div style="text-align:center; min-width:170px;">
            <div style="font-size:0.9rem; color:#6b7280; font-weight:700;">최종 판정</div>
            <div style="font-size:2.4rem; font-weight:900; color:{v['color']}; line-height:1.15;">
              {v['icon']} {result.verdict}
            </div>
            <div style="font-size:1.0rem; font-weight:700; color:{v['color']};">
              스코어 {result.score:+d}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # 스코어 게이지(-100~+100 → 0~100)
    st.progress(int((result.score + 100) / 2))


def kpi_row(result) -> None:
    """핵심 지표 KPI 카드 행."""
    ind = result.indicators
    rsi = ind.get("rsi")
    rsi_val = float(rsi.dropna().iloc[-1]) if rsi is not None and not rsi.dropna().empty else None
    macd_df = ind.get("macd")
    macd_state = "-"
    if macd_df is not None and len(macd_df) >= 1:
        macd_state = "매수(+)" if macd_df["MACD"].iloc[-1] > macd_df["Signal"].iloc[-1] else "매도(-)"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("종합 스코어", f"{result.score:+d}", help="-100(강한 하락) ~ +100(강한 상승)")
    c2.metric("상승 근거", ind.get("bull_score", 0))
    c3.metric("하락 근거", ind.get("bear_score", 0))
    c4.metric("RSI(14)", f"{rsi_val:.0f}" if rsi_val is not None else "-",
              help="70↑ 과매수 / 30↓ 과매도")
    c5.metric("MACD", macd_state)
    if ind.get("squeeze"):
        st.info("🔎 볼린저밴드 스퀴즈(변동성 수축) → 곧 큰 방향성이 나올 수 있습니다. 방향은 거래량으로 확인.")


def _chips(reasons, color, chip_bg) -> str:
    if not reasons:
        return "<div style='color:#9ca3af; font-size:0.9rem;'>해당 없음</div>"
    html = ""
    for r in reasons:
        detail = f" <small>{r.detail}</small>" if r.detail else ""
        html += (f"<span class='chip' style='background:{chip_bg}; color:{color};'>"
                 f"{r.label}{detail}</span>")
    return html


def reason_columns(reasons) -> None:
    """판정 근거를 상승/하락/참고 3열 색상 카드 + 칩으로 그룹핑."""
    bull = [r for r in reasons if r.direction == "bull"]
    bear = [r for r in reasons if r.direction == "bear"]
    other = [r for r in reasons if r.direction in ("neutral", "na")]

    col1, col2, col3 = st.columns(3)
    with col1:
        d = DIRECTION["bull"]
        st.markdown(f"<div class='st-card' style='border-top:4px solid {d['color']};'>"
                    f"<h4>▲ 상승 근거 ({len(bull)})</h4>{_chips(bull, d['color'], d['chip'])}</div>",
                    unsafe_allow_html=True)
    with col2:
        d = DIRECTION["bear"]
        st.markdown(f"<div class='st-card' style='border-top:4px solid {d['color']};'>"
                    f"<h4>▼ 하락 근거 ({len(bear)})</h4>{_chips(bear, d['color'], d['chip'])}</div>",
                    unsafe_allow_html=True)
    with col3:
        d = DIRECTION["neutral"]
        st.markdown(f"<div class='st-card' style='border-top:4px solid {d['color']};'>"
                    f"<h4>• 참고 ({len(other)})</h4>{_chips(other, d['color'], d['chip'])}</div>",
                    unsafe_allow_html=True)


def section_title(text: str) -> None:
    st.markdown(f"<div class='sec-title'>{text}</div>", unsafe_allow_html=True)

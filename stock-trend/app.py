"""홈 / 랜딩 (Streamlit 멀티페이지 엔트리).

실행: streamlit run app.py
왼쪽 사이드바에서 페이지(추세 판정 / 퀀트)를 선택한다.
공용 로직은 core/ 패키지, 도메인은 trend_service/·quant_service/에 있다.
"""
from __future__ import annotations

import streamlit as st

import ui
from core import krx_api
from core.env import sync_secrets

sync_secrets()

st.set_page_config(page_title="주식 분석 플랫폼", page_icon="📊", layout="wide")
ui.inject_css()

st.title("📊 주식 분석 플랫폼")
st.caption("추세 판정과 퀀트 투자 도구를 한 곳에서. 국내(KRX) 우선 · 미국 확장 대비.")

st.warning(
    "⚠️ 투자 자문이 아닙니다. 모든 지표·전략은 확률을 높이는 참고 도구이며, "
    "실제 투자 판단과 손실 책임은 본인에게 있습니다."
)

c1, c2 = st.columns(2)
with c1:
    st.markdown(
        """
        ### 📈 추세 판정
        종목 티커를 입력하면 이동평균·거래량·RSI/MACD·볼린저·엔벨로프·시장심리를
        종합해 **상승/하락/중립**을 근거·차트와 함께 판정합니다.
        - 관심종목(즐겨찾기) · 백테스트 · 투자자별 수급
        """
    )
    st.page_link("pages/1_📈_추세판정.py", label="추세 판정 열기 →")

with c2:
    st.markdown(
        """
        ### 🧮 퀀트 스크리너
        코스피200·코스닥150 유니버스에서 **밸류·퀄리티·모멘텀** 팩터로
        종목을 랭킹합니다. (기본 가중치 밸류 40 / 퀄리티 30 / 모멘텀 30)
        - 다음: 포트폴리오 백테스트 → 미국 확장
        """
    )
    st.page_link("pages/2_🧮_퀀트_스크리너.py", label="퀀트 스크리너 열기 →")

st.divider()
st.markdown(
    """
    ### 📊 상승/하락 예측 랭킹 *(코스피200)*
    추세판정 점수 + 수급(외국인·기관·개인) + 매크로를 블렌드해 **상승 가능성 TOP / 하락 가능성 TOP**을 뽑습니다.
    """
)
st.page_link("pages/3_📊_상승하락_예측.py", label="상승/하락 예측 열기 →")

st.divider()
if krx_api.api_key():
    st.caption("🟢 국내 시세: 금융위원회 주식시세정보 API · 미국 시세: yfinance")
else:
    st.caption("⚪ 국내 시세: yfinance 폴백 (환경변수 `DATA_GO_KR_API_KEY` 설정 시 금융위 API) · 미국: yfinance")

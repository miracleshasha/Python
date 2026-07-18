"""plotly 차트 생성.

캔들스틱 + 이동평균 오버레이 + 거래량 + RSI/MACD 서브플롯을 하나의 Figure로 만든다.
UI(app.py)는 이 Figure를 그대로 렌더링만 하면 된다.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import config


def build_chart(df: pd.DataFrame, result, title: str = "") -> go.Figure:
    """가격/거래량/RSI/MACD 4단 차트."""
    ind = result.indicators
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        row_heights=[0.5, 0.15, 0.175, 0.175],
        vertical_spacing=0.03,
        subplot_titles=(title or "가격 + 이동평균", "거래량", "RSI(14)", "MACD"),
    )

    # 1) 캔들 + MA
    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="가격",
        ),
        row=1, col=1,
    )
    mas = ind.get("ma")
    if mas is not None:
        for col in mas.columns:
            fig.add_trace(
                go.Scatter(x=mas.index, y=mas[col], name=col, mode="lines"),
                row=1, col=1,
            )

    # 볼린저밴드 (변동성 기반, 점선 · 상하단 사이 음영)
    bb = ind.get("bollinger")
    if bb is not None:
        fig.add_trace(go.Scatter(x=bb.index, y=bb["Upper"], name="볼린저 상단",
                                 line=dict(color="rgba(120,120,200,0.7)", dash="dot", width=1)),
                      row=1, col=1)
        fig.add_trace(go.Scatter(x=bb.index, y=bb["Lower"], name="볼린저 하단",
                                 line=dict(color="rgba(120,120,200,0.7)", dash="dot", width=1),
                                 fill="tonexty", fillcolor="rgba(120,120,200,0.08)"),
                      row=1, col=1)

    # 엔벨로프 (고정 비율 기반, 파선)
    env = ind.get("envelope")
    if env is not None:
        fig.add_trace(go.Scatter(x=env.index, y=env["Upper"], name="엔벨로프 상단",
                                 line=dict(color="rgba(220,120,60,0.8)", dash="dash", width=1)),
                      row=1, col=1)
        fig.add_trace(go.Scatter(x=env.index, y=env["Lower"], name="엔벨로프 하단",
                                 line=dict(color="rgba(220,120,60,0.8)", dash="dash", width=1)),
                      row=1, col=1)

    # 2) 거래량
    vol = ind.get("volume")
    if vol is not None:
        fig.add_trace(go.Bar(x=vol.index, y=vol, name="거래량", showlegend=False),
                      row=2, col=1)

    # 3) RSI
    rsi_s = ind.get("rsi")
    if rsi_s is not None:
        fig.add_trace(go.Scatter(x=rsi_s.index, y=rsi_s, name="RSI", showlegend=False),
                      row=3, col=1)
        fig.add_hline(y=config.RSI_OVERBOUGHT, line_dash="dot", line_color="red", row=3, col=1)
        fig.add_hline(y=config.RSI_OVERSOLD, line_dash="dot", line_color="blue", row=3, col=1)

    # 4) MACD
    macd_df = ind.get("macd")
    if macd_df is not None:
        fig.add_trace(go.Bar(x=macd_df.index, y=macd_df["Hist"], name="Hist", showlegend=False),
                      row=4, col=1)
        fig.add_trace(go.Scatter(x=macd_df.index, y=macd_df["MACD"], name="MACD"),
                      row=4, col=1)
        fig.add_trace(go.Scatter(x=macd_df.index, y=macd_df["Signal"], name="Signal"),
                      row=4, col=1)

    fig.update_layout(
        height=800,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=60, b=20),
    )
    return fig

# 📈 종목 추세 판단 웹 서비스

종목 티커를 입력하면 **상승 / 하락 / 중립** 추세를 근거와 함께 판정해 주는 Streamlit 웹 서비스입니다.
이동평균 기울기, 거래량/OBV, RSI/MACD/볼린저밴드, VIX·SOX 시장심리, (국내) 외국인 수급을
규칙으로 종합합니다.

> ⚠️ **투자 자문이 아닙니다.** 기술적 지표는 확률을 높이는 참고 도구일 뿐이며, 어떤 조합도 100%
> 적중하지 않습니다. 실제 투자 판단과 손실 책임은 본인에게 있습니다.

## 빠른 시작

```bash
cd stock-trend
python -m venv .venv && source .venv/bin/activate   # (선택)
pip install -r requirements.txt
streamlit run app.py
```

브라우저가 열리면 티커를 입력하고 **분석**을 누르세요.
- 한국 종목: 6자리 코드 — `005930`(삼성전자), `000660`(SK하이닉스), 코스닥은 `.KQ`
- 미국 종목: 심볼 — `AAPL`, `NVDA`

## 판정 방식

| 상승 근거(+) | 하락 근거(−) |
|---|---|
| 60일선 기울기 우상향 | 60일선 기울기 꺾임 |
| 20일선 위 종가 + 거래량 급증 | 20일선 이탈 후 회복 실패 |
| 골든크로스(20>60) | 데드크로스(20<60) |
| SOX(반도체) 20일선 위 | 약세 다이버전스(RSI/OBV) |
| VIX 안정/하락 | VIX 급등 + SOX 급락 |
| 외국인 3일↑ 순매수(국내) | 외국인 5일↑ 순매도(국내) |

각 항목에 가중치를 두고 `(상승근거 − 하락근거)`를 **−100 ~ +100** 스코어로 환산한 뒤,
임계값(기본 ±25)으로 상승/중립/하락을 구분합니다. 모든 파라미터는 `config.py`에서 조정할 수 있습니다.

## 구조

```
stock-trend/
├── app.py                 # Streamlit UI
├── config.py              # 지표 파라미터 · 판정 임계값 · 가중치
├── requirements.txt
├── trend_service/
│   ├── data.py            # yfinance OHLCV + VIX/SOX + (선택)외국인 수급
│   ├── indicators.py      # 지표 계산 (순수 함수)
│   ├── engine.py          # 체크리스트 규칙 → 추세 판정
│   └── charts.py          # plotly 차트
└── tests/
    └── test_indicators.py # 지표 단위 테스트
```

로직 계층(`trend_service`)과 UI(`app.py`)를 분리해, 추후 FastAPI 등 다른 프론트에서
그대로 재사용할 수 있습니다.

## 테스트

```bash
cd stock-trend
pytest tests/ -v
```

## 선택 기능: 국내 외국인 수급

`requirements.txt`에서 `pykrx` 주석을 해제하고 설치하면, 국내 종목에 한해 외국인 순매수/순매도
연속일 신호가 판정에 반영됩니다. 설치돼 있지 않아도 나머지 기능은 정상 동작합니다.

## 향후 계획 (v1 이후)

로그인/관심종목 저장, 실시간 알림, 백테스팅, FastAPI 백엔드 분리 배포.

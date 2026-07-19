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

## 데이터 소스

| 대상 | 소스 | 비고 |
|---|---|---|
| **국내 종목 시세** | 금융위원회 주식시세정보 API (data.go.kr) | 인증키 필요, 없으면 yfinance로 폴백 |
| 미국 종목 시세 | yfinance | |
| VIX / SOX 지수 | yfinance | |
| 외국인·기관·개인 수급 | pykrx (기본 포함) | 국내 종목만 · 금융위 API엔 없는 데이터라 별도 소스 |

### 국내 시세 API 인증키 설정

[공공데이터포털](https://www.data.go.kr)에서 **금융위원회_주식시세정보**를 활용신청해 받은
일반 인증키를 **환경변수**로 지정하세요 (코드/레포에 넣지 마세요):

```bash
export DATA_GO_KR_API_KEY="발급받은_일반_인증키"
streamlit run app.py
```

키가 설정되면 국내 종목(6자리 코드)은 이 API로 조회하고 종목명도 함께 가져옵니다.
키가 없으면 자동으로 yfinance로 폴백합니다.

> 📦 **배포**: 로컬 실행 / Streamlit Community Cloud(무료) / Docker 배포 방법은
> [`DEPLOY.md`](DEPLOY.md)를 참고하세요. (Vercel은 Streamlit에 부적합 — 이유도 문서에 설명)

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

## 기능

- **🔍 단일 분석** — 티커 하나의 추세를 **최종 결과 강조 박스**·근거·차트와 함께 판정.
  종목명(회사명)을 함께 표시하고, 국내 종목은 **외국인·기관·개인 수급**을 표/막대차트로 보여줌.
  가격 차트에 이동평균·**볼린저밴드**·**엔벨로프(±6%)**를 오버레이.
- **⭐ 워치리스트** — 관심종목을 저장하고 전 종목 판정을 표로 한눈에 (`data/watchlist.json`)
- **🧪 백테스트** — 과거 각 시점에서 그 시점까지의 데이터만으로(look-ahead 없음) 판정하고,
  이후 보유기간 수익률을 집계해 상승/하락 신호별 **적중률·평균 수익률**을 검증
- **🔔 자동 스캔** — `scan.py`가 워치리스트를 순회해 매수/청산 신호를 알림 로그로 남김(cron 연동)
- **🧮 퀀트 스크리너** — 코스피200·코스닥150 유니버스에서 **밸류·퀄리티·모멘텀** 팩터
  z-score 가중합(기본 40/30/30)으로 종목 랭킹. 데이터는 pykrx(국내 네트워크 필요)
- **📊 상승/하락 예측 랭킹**(코스피200 한정) — 추세판정 점수 + 수급(외국인·기관·개인) + 매크로(KOSPI·VIX·SOX)를
  블렌드(기본 50/30/20)해 **상승 가능성 TOP / 하락 가능성 TOP**을 산출
- **🔎 종목명 검색** — 종목명으로 검색하면 티커가 자동 입력(추세판정 페이지)

## 구조

Streamlit **멀티페이지** 앱이며, 공용 로직은 `core/` 패키지에, 도메인은 `trend_service/`
(추후 `quant_service/`)에 둡니다. 추세 판정과 향후 퀀트 기능이 데이터·지표·차트·관심종목을
공유하며 **공존**합니다.

```
stock-trend/
├── app.py                 # 홈/랜딩 (멀티페이지 엔트리)
├── pages/
│   ├── 1_📈_추세판정.py    # 추세 판정 UI (단일분석 / 워치리스트 / 백테스트)
│   ├── 2_🧮_퀀트_스크리너.py # 팩터(밸류·퀄리티·모멘텀) 랭킹
│   └── 3_📊_상승하락_예측.py  # 코스피200 상승/하락 예측 랭킹
├── scan.py                # 워치리스트 자동 스캔 CLI (cron용)
├── ui.py                  # 공통 UI 컴포넌트/CSS
├── config.py              # 지표·판정·백테스트·(향후)퀀트 파라미터
├── requirements.txt
├── core/                  # ★ 공용 인프라 (추세·퀀트 공유)
│   ├── markets.py         # 시장 구분(KR/US) · 티커 정규화 (미국 확장 seam)
│   ├── data.py            # 금융위 API/yfinance OHLCV + VIX/SOX + pykrx 투자자 수급
│   ├── krx_api.py         # 금융위 주식시세정보 API 클라이언트
│   ├── indicators.py      # 지표 계산 (순수 함수)
│   ├── charts.py          # plotly 차트
│   ├── watchlist.py       # 관심종목 JSON 저장/관리
│   ├── notify.py          # 알림 채널(콘솔/파일, 이메일·Slack 확장점)
│   ├── env.py             # Streamlit Secrets → 환경변수 브리지
│   ├── cache.py           # 날짜 키 디스크 캐시(대량 횡단면 조회용)
│   ├── universe.py        # 지수 구성종목(코스피200·코스닥150)
│   ├── fundamentals.py    # PER·PBR·ROE·배당·시총·모멘텀 스냅샷
│   ├── flows.py           # 투자자별 순매수(외국인·기관·개인) 횡단면
│   ├── macro.py           # 매크로 시장 레짐(KOSPI·VIX·SOX)
│   ├── listings.py        # 종목명↔티커(종목명 검색, fdr+폴백)
│   └── providers/         # 시장별 데이터 어댑터(krx.py = pykrx, 향후 us.py)
├── trend_service/         # 추세 판정 도메인 (core 재사용)
│   ├── engine.py          # evaluate_price(포인트인타임 코어) + analyze(시장맥락)
│   └── backtest.py        # 포인트인타임 백테스트
├── quant_service/         # 퀀트 도메인
│   ├── factors.py         # 팩터 z-score(밸류·퀄리티·모멘텀)
│   └── screener.py        # 합성점수 랭킹·상위 N 선정
├── prediction_service/    # 상승/하락 예측 랭킹 도메인
│   └── ranking.py         # 추세+수급+매크로 블렌드 → 상승/하락 TOP
└── tests/                 # indicators/engine/watchlist/backtest/krx_api/factors/screener/ranking
```

**계층 분리**: 공용 `core/`(데이터·지표·차트) → 도메인 `trend_service/`(엔진) → UI(`app.py`, `pages/`).
미국 확장은 `core/markets.py`·(향후) `core/providers/`에 시장 어댑터를 추가하면 됩니다.
`engine.evaluate_price()`는 네트워크 없이 가격만으로 판정하는 포인트인타임 코어로,
백테스트가 과거 시점마다 look-ahead 없이 재사용합니다.

## 자동 스캔 (알림)

```bash
python scan.py                 # 워치리스트 전체 스캔
python scan.py 005930 AAPL     # 특정 티커만
python scan.py --all           # 중립 종목도 출력
```

매수(상승)/청산(하락) 신호가 잡히면 콘솔과 `data/alerts.log`에 기록됩니다. 정기 실행 예:

```cron
0 16 * * 1-5  cd /path/to/stock-trend && python scan.py >> data/scan.out 2>&1
```

### 알림 확장 (이메일/Slack)

`trend_service/notify.py`의 `send_email` / `send_slack`은 확장점만 남겨둔 상태입니다.
실제 발송을 붙이려면 해당 함수를 구현하고 SMTP 계정·Slack Webhook 등 시크릿을 환경변수로
주입하세요. (기본 제공 기능은 크리덴셜이 필요 없는 콘솔/파일 알림입니다.)

## 테스트

```bash
cd stock-trend
pytest tests/ -v
```

## 국내 투자자별 수급 (외국인·기관·개인)

투자자별 수급은 **금융위 주식시세정보 API에는 없는 데이터**라, `pykrx`(KRX)로 별도 조회합니다.
`pykrx`는 `requirements.txt`에 기본 포함되어 `pip install -r requirements.txt` 시 함께 설치됩니다.
설치 후 국내 종목의 외국인·기관·개인 순매수가 단일 분석 화면에 표시되고, 외국인 순매수/순매도
연속일 신호가 판정에도 반영됩니다.

> pykrx는 KRX 사이트를 조회하므로 **국내 네트워크가 열려 있어야** 동작합니다(휴장/차단 시 미표시).

## 향후 계획 (v1 이후)

로그인/관심종목 저장, 실시간 알림, 백테스팅, FastAPI 백엔드 분리 배포.

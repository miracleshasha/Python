"""추세 판단 서비스 전역 설정.

지표 파라미터와 판정 임계값을 한곳에 모아 튜닝하기 쉽게 한다.
값의 근거는 사용자가 정리한 실전 지표 체계(README 참고).
"""

# --- 이동평균 ---
MA_PERIODS = [20, 60, 120]          # 단기/중기/장기
MA_SLOPE_LOOKBACK = 5               # 기울기 계산 기간(최근 N일)

# --- 거래량 ---
VOLUME_AVG_WINDOW = 20              # 거래량 평균 기준일
VOLUME_SURGE_RATIO = 1.5           # 평균 대비 150% 이상이면 "급증"

# --- RSI ---
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# --- MACD ---
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# --- 볼린저밴드 ---
BB_PERIOD = 20
BB_STD = 2.0
BB_SQUEEZE_QUANTILE = 0.25         # 밴드폭이 하위 25%면 스퀴즈로 간주

# --- 엔벨로프 ---
ENVELOPE_PERIOD = 20               # 중심 이동평균 기간
ENVELOPE_PCT = 0.06                # 중심선 ± 6% 밴드

# --- 시장심리(VIX) ---
VIX_CALM = 15                      # 과도한 안심
VIX_NORMAL = 20
VIX_FEAR = 30                      # 공포
VIX_SPIKE_PCT = 0.20               # 하루 20%↑ 급등 = 시장 충격

# --- 다이버전스 탐지 ---
DIVERGENCE_LOOKBACK = 20           # 최근 고점/저점 비교 구간

# --- 판정 스코어링 ---
# 각 체크리스트 항목의 가중치. 상승 근거는 +, 하락 근거는 -.
BULL_WEIGHTS = {
    "ma60_slope_up": 25,           # 60일선 기울기 우상향
    "above_ma20_with_volume": 20,  # 20일선 위 종가 + 거래량 급증
    "sox_above_ma20": 15,          # SOX 20일선 위
    "foreign_net_buy": 15,         # 외국인 3일↑ 순매수(국내만)
    "vix_calm": 10,                # VIX 25 이하 또는 하락
    "golden_cross": 15,            # 20>60 골든크로스
}
BEAR_WEIGHTS = {
    "bearish_divergence": 25,      # OBV/RSI 다이버전스
    "break_ma20": 20,              # 20일선 이탈 + 회복 실패
    "vix_spike_sox_drop": 20,      # VIX 급등 + SOX 급락
    "foreign_net_sell": 15,        # 외국인 순매도 5일↑
    "dead_cross": 15,              # 20<60 데드크로스
    "ma60_slope_down": 25,         # 60일선 기울기 꺾임
}

# 최종 스코어(-100~+100) → 판정 구간
VERDICT_BULL_THRESHOLD = 25        # 이 이상이면 상승
VERDICT_BEAR_THRESHOLD = -25       # 이 이하면 하락

# --- 백테스트 ---
BACKTEST_HORIZON = 20              # 신호 발생 후 성과 측정 보유기간(거래일)

# --- 데이터 ---
DEFAULT_PERIOD = "1y"
CACHE_TTL_SECONDS = 60 * 15        # 15분 캐시
MARKET_INDEX_VIX = "^VIX"
MARKET_INDEX_SOX = "^SOX"

# --- 퀀트 (스크리너/포트폴리오) ---
# 유니버스: pykrx 지수 코드 (코스피200=1028, 코스닥150=2203)
QUANT_UNIVERSE_INDICES = {"코스피200": "1028", "코스닥150": "2203"}
# 지수 코드 → 소속 시장(펀더멘털 횡단면 조회용)
QUANT_INDEX_MARKET = {"1028": "KOSPI", "2203": "KOSDAQ"}
# 팩터 가중치(밸류/퀄리티/모멘텀). 합이 100이 아니어도 내부에서 정규화.
QUANT_FACTOR_WEIGHTS = {"value": 40, "quality": 30, "momentum": 30}
QUANT_MOMENTUM_MONTHS = 6          # 모멘텀 측정 기간(개월)
QUANT_TOP_N = 20                   # 상위 몇 종목 선정
QUANT_ZSCORE_CLIP = 3.0            # z-score 이상치 클리핑(±)
QUANT_EXCLUDE_PREFERRED = True     # 우선주(코드 끝자리≠0) 제외
QUANT_REBALANCE = "quarterly"      # 리밸런싱 주기(백테스트용): quarterly/monthly

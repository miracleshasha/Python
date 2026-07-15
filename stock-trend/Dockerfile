# 종목 추세 판단 서비스 — 컨테이너 이미지 (Render/Railway/Fly.io/HF Spaces 등)
FROM python:3.11-slim

WORKDIR /app

# 의존성 먼저 설치(캐시 활용)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 소스 복사
COPY . .

# 호스트가 주는 $PORT를 사용(없으면 8501)
ENV PORT=8501
EXPOSE 8501

# 인증키는 런타임 환경변수로 주입: -e DATA_GO_KR_API_KEY=...
CMD ["sh", "-c", "streamlit run app.py --server.port ${PORT} --server.address 0.0.0.0"]

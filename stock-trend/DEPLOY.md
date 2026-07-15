# 배포 가이드

> **왜 필요한가:** 개발 샌드박스 등 일부 환경은 아웃바운드 네트워크가 막혀 있어
> 실시간 시세(data.go.kr / Yahoo)를 못 부릅니다. **인터넷이 열린 곳에서 실행하면 해결**됩니다.
> 아래 세 경로 중 편한 것을 고르세요.

인증키(`DATA_GO_KR_API_KEY`)는 **어디서도 코드/레포에 넣지 말고** 환경변수나 Secrets로만 주입하세요.

---

## ① 로컬 실행 (가장 빠름)

```bash
cd stock-trend
pip install -r requirements.txt
export DATA_GO_KR_API_KEY="발급받은_일반_인증키"   # Windows PowerShell: $env:DATA_GO_KR_API_KEY="..."
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속 → 국내 종목(예: `005930`) 실데이터 확인.

---

## ② Streamlit Community Cloud (무료, 권장)

Streamlit 전용 호스팅이라 이 앱과 100% 호환됩니다.

1. 이 레포를 GitHub에 push (이미 되어 있음).
2. <https://share.streamlit.io> 로그인 → **New app**.
3. 설정:
   - Repository: `miracleshasha/Python`
   - Branch: 배포할 브랜치
   - **Main file path: `stock-trend/app.py`**
4. **Advanced settings → Secrets** 에 아래를 붙여넣기:
   ```toml
   DATA_GO_KR_API_KEY = "발급받은_일반_인증키"
   ```
5. **Deploy** → `*.streamlit.app` 공개 URL 생성.

> 앱은 `st.secrets` 의 키를 자동으로 환경변수로 옮겨 사용합니다(`app.py` 상단 브리지).

---

## ③ Docker (Render / Railway / Fly.io / Hugging Face Spaces 등)

```bash
cd stock-trend
docker build -t stock-trend .
docker run -p 8501:8501 -e DATA_GO_KR_API_KEY="발급받은_일반_인증키" stock-trend
```

호스팅 플랫폼에서는 `PORT` 환경변수와 `DATA_GO_KR_API_KEY` 시크릿을 설정하면 됩니다.

---

## ❌ Vercel은 권장하지 않음

Vercel은 **서버리스/프론트엔드(Next.js) 중심**이라, WebSocket 기반으로 **상시 실행**되는
Streamlit 서버와 맞지 않습니다. Vercel에 올리려면 프론트를 Next.js로, 판정 로직을 서버리스
API(`/api/*`)로 **전면 재작성**해야 합니다. 그럴 계획이 아니라면 위 ①~③을 사용하세요.
(로직은 `trend_service/`에 UI와 분리돼 있어, 필요 시 FastAPI/서버리스 백엔드로 재사용 가능합니다.)

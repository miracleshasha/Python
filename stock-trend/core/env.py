"""환경/시크릿 헬퍼.

Streamlit Secrets에 담긴 키를 환경변수로 옮겨, streamlit 비의존 모듈(core.krx_api 등)이
그대로 인식하도록 브리지한다. 각 페이지 시작부에서 sync_secrets()를 호출한다.
"""
from __future__ import annotations

import os

_KEYS = ("DATA_GO_KR_API_KEY",)


def sync_secrets() -> None:
    """st.secrets → os.environ 브리지 (secrets 없거나 streamlit 없으면 무해하게 통과)."""
    try:
        import streamlit as st
        for k in _KEYS:
            if k in st.secrets and not os.environ.get(k):
                os.environ[k] = str(st.secrets[k])
    except Exception:
        pass

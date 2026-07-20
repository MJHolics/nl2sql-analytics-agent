"""제공자 무관 LLM 클라이언트. Gemini(무료 티어) 기본, Vertex·Anthropic·OpenAI 옵션.

키 자동 선택 우선순위(LLM_PROVIDER=auto): gemini → anthropic → openai.
Vertex(엔터프라이즈)는 명시적으로 LLM_PROVIDER=vertex 일 때만 쓴다 — API 키가 아니라
GCP ADC(서비스계정/gcloud)로 인증하고 과금되므로 자동선택에는 넣지 않는다.
각 SDK는 실제 사용하는 제공자만 설치하면 된다.
"""
from __future__ import annotations

import os

import config


def _detect_provider() -> str:
    p = config.LLM_PROVIDER.lower()
    if p != "auto":
        return p
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    raise RuntimeError(
        "LLM API 키가 없습니다. GEMINI_API_KEY(무료: aistudio.google.com) 또는 "
        "ANTHROPIC_API_KEY / OPENAI_API_KEY 중 하나를 설정하세요."
    )


class LLM:
    def __init__(self) -> None:
        self.provider = _detect_provider()
        self.model = config.LLM_MODEL[self.provider]
        self._client = None  # 지연 초기화

    # --- 공개 API ---
    def complete(self, system: str, user: str, temperature: float = 0.0) -> str:
        """system+user 프롬프트로 한 번 호출하고 텍스트만 반환.
        무료 티어 rate limit(429) 시 서버가 알려준 지연만큼 기다려 재시도."""
        fn = {
            "gemini": self._gemini,
            "vertex": self._vertex,
            "anthropic": self._anthropic,
            "openai": self._openai,
        }.get(self.provider)
        if fn is None:
            raise ValueError(f"알 수 없는 provider: {self.provider}")
        last: Exception | None = None
        for _ in range(3):
            try:
                return fn(system, user, temperature)
            except Exception as e:  # rate limit만 재시도, 그 외는 즉시 전파
                s = str(e)
                if "429" not in s and "RESOURCE_EXHAUSTED" not in s and "rate limit" not in s.lower():
                    raise
                import re
                import time

                m = re.search(r"retryDelay\D+(\d+)", s)
                time.sleep(min(int(m.group(1)) if m else 5, 30))
                last = e
        raise last  # type: ignore[misc]

    # --- 제공자별 구현 ---
    def _gemini(self, system: str, user: str, temperature: float) -> str:
        if self._client is None:
            from google import genai

            key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            self._client = genai.Client(api_key=key)
        from google.genai import types

        resp = self._client.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system, temperature=temperature
            ),
        )
        return (resp.text or "").strip()

    def _vertex(self, system: str, user: str, temperature: float) -> str:
        """Vertex AI Gemini. 같은 google-genai SDK를 vertexai 모드로 쓴다(API 키 대신 ADC).

        이노션류 'Vertex AI' 요구의 엔터프라이즈 경로 — 무료 Gemini 키 코드와 한 줄 차이로
        전환된다(provider 무관 설계). 인증은 GCP ADC, 청구는 GOOGLE_CLOUD_PROJECT.
        """
        if self._client is None:
            from google import genai

            self._client = genai.Client(
                vertexai=True,
                project=os.getenv("GOOGLE_CLOUD_PROJECT"),
                location=config.VERTEX_LOCATION,
            )
        from google.genai import types

        resp = self._client.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system, temperature=temperature
            ),
        )
        return (resp.text or "").strip()

    def _anthropic(self, system: str, user: str, temperature: float) -> str:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        msg = self._client.messages.create(
            model=self.model,
            max_tokens=2048,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if b.type == "text").strip()

    def _openai(self, system: str, user: str, temperature: float) -> str:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = self._client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (resp.choices[0].message.content or "").strip()

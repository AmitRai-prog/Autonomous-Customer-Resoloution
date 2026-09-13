"""
LLM Provider connectors for Google Gemini and NVIDIA NIM.
Handles structured JSON responses, API key validation, and resilient offline fallbacks.
"""

import os
import json
import re
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
SIMULATED_AI = os.environ.get("SIMULATED_AI", "false").lower() in ("true", "1", "yes")

_gemini_client = None
_nvidia_client = None


def has_valid_key(key: Optional[str]) -> bool:
    if not key:
        return False
    placeholder_tokens = ["YOUR_", "your_", "here", "xxx", "placeholder"]
    return not any(token in key for token in placeholder_tokens)


def get_gemini_client():
    global _gemini_client
    if _gemini_client is None and has_valid_key(GEMINI_API_KEY):
        try:
            from google import genai
            _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception as e:
            print(f"[LLM] Gemini client init warning: {e}")
    return _gemini_client


def get_nvidia_client():
    global _nvidia_client
    if _nvidia_client is None and has_valid_key(NVIDIA_API_KEY):
        try:
            from openai import OpenAI
            _nvidia_client = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=NVIDIA_API_KEY
            )
        except Exception as e:
            print(f"[LLM] NVIDIA client init warning: {e}")
    return _nvidia_client


def clean_json_response(raw_text: str) -> str:
    """Extract clean JSON from model output that might contain markdown fences."""
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)
    return raw_text.strip()


def call_llm_json(
    prompt: str,
    system_prompt: str,
    output_schema: Optional[Type[BaseModel]] = None,
    temperature: float = 0.1
) -> Dict[str, Any]:
    """
    Calls Google Gemini with JSON enforcement.
    Returns a parsed Python dictionary.
    """
    client = get_gemini_client()
    if client and not SIMULATED_AI:
        try:
            full_prompt = f"{system_prompt}\n\nStrictly output valid JSON only matching the schema.\n\nInput:\n{prompt}"
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=full_prompt,
                config={"response_mime_type": "application/json"}
            )
            cleaned = clean_json_response(response.text)
            return json.loads(cleaned)
        except Exception as e:
            print(f"[LLM] Gemini call failed, falling back: {e}")

    # Return empty dict if no live LLM available (caller will use deterministic agent logic)
    return {}


def call_nvidia_llm(
    prompt: str,
    system_prompt: str,
    model: str = "meta/llama3-70b-instruct"
) -> str:
    """
    Calls NVIDIA NIM LLM for generation step in Policy RAG.
    """
    client = get_nvidia_client()
    if client and not SIMULATED_AI:
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1,
                max_tokens=1024
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            print(f"[LLM] NVIDIA NIM call failed, falling back: {e}")

    return ""

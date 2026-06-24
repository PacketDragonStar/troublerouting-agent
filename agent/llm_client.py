"""LLM 客户端——调用 DeepSeek/OpenAI API 进行文本分析"""
import os
from typing import Optional


class LLMClient:
    """通用 LLM 调用客户端（OpenAI 兼容 API）"""

    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
        self.model = os.getenv("LLM_MODEL", "deepseek-chat")

    def analyze(self, prompt: str, system: str = "") -> Optional[str]:
        """发送分析请求并返回 LLM 回复"""
        if not self.api_key:
            return None
        try:
            import httpx
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system or "你是网络排障专家，擅长分析设备CLI输出。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=90.0,
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  [LLM-ERR] {e}")
            return None
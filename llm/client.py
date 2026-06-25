import base64
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

import requests
from PIL import Image

from config import config
from utils.logger import logger


@dataclass
class LLMResponse:
    content: str
    finish_reason: str | None = None
    usage: dict | None = None


class LLMClient:
    def __init__(self, base_url: str | None = None, model: str | None = None, context_size: int | None = None):
        self.base_url = base_url or config.LLM_BASE_URL
        self.model = model or config.LLM_MODEL
        self.context_size = context_size or config.LLM_CONTEXT_SIZE
        logger.info(f"LLM client initialized: {self.base_url}, model={self.model}, context={self.context_size}")

    @staticmethod
    def _trim_to_context(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        half = max_chars // 2
        return text[:half] + "\n...[truncated]...\n" + text[-half:]

    def _image_to_base64(self, image: Image.Image, format: str = "PNG") -> str:
        buffer = BytesIO()
        image.save(buffer, format=format)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _build_payload(self, system_prompt: str, user_text: str, temperature: float,
                       max_tokens: int, response_format: Optional[dict] = None,
                       is_vision: bool = False) -> dict:
        # Rough estimate: 1 token ≈ 4 chars. Reserve for system prompt + output.
        reserved_system = len(system_prompt)
        reserved_output = max_tokens * 4
        max_user_chars = max(200, self.context_size * 4 - reserved_system - reserved_output)
        trimmed = self._trim_to_context(user_text, max_user_chars)

        messages = [
            {"role": "system", "content": system_prompt},
        ]
        if is_vision:
            messages.append({"role": "user", "content": [
                {"type": "text", "text": trimmed},
            ]})
        else:
            messages.append({"role": "user", "content": trimmed})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "cache_prompt": False,
        }
        if response_format:
            payload["response_format"] = response_format
        return payload

    def vision_chat(
        self,
        system_prompt: str,
        user_text: str,
        image: Image.Image,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> Optional[LLMResponse]:
        b64_image = self._image_to_base64(image)
        payload = self._build_payload(system_prompt, user_text, temperature, max_tokens, is_vision=True)
        # Insert image into the vision content array
        payload["messages"][1]["content"].append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64_image}"},
        })

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            return LLMResponse(
                content=choice["message"]["content"],
                finish_reason=choice.get("finish_reason"),
                usage=data.get("usage"),
            )
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to llama-server at {self.base_url}")
            return None
        except Exception as e:
            logger.error(f"LLM vision call failed: {e}")
            return None

    def text_chat(
        self,
        system_prompt: str,
        user_text: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
        response_format: Optional[dict] = None,
    ) -> Optional[LLMResponse]:
        payload = self._build_payload(system_prompt, user_text, temperature, max_tokens, response_format)

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            return LLMResponse(
                content=choice["message"]["content"],
                finish_reason=choice.get("finish_reason"),
                usage=data.get("usage"),
            )
        except requests.exceptions.ConnectionError:
            logger.error(f"Cannot connect to llama-server at {self.base_url}")
            return None
        except Exception as e:
            logger.error(f"LLM text call failed: {e}")
            return None

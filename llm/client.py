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
    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = base_url or config.LLM_BASE_URL
        self.model = model or config.LLM_MODEL
        logger.info(f"LLM client initialized: {self.base_url}, model={self.model}")

    def _image_to_base64(self, image: Image.Image, format: str = "PNG") -> str:
        buffer = BytesIO()
        image.save(buffer, format=format)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def vision_chat(
        self,
        system_prompt: str,
        user_text: str,
        image: Image.Image,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> Optional[LLMResponse]:
        b64_image = self._image_to_base64(image)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64_image}"},
                        },
                    ],
                },
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

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
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

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

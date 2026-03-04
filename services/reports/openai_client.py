import os
import json
import asyncio
import logging
import aiohttp
from typing import Optional, AsyncGenerator

from core.abstractions.illm_client import ILLMClient, ChatMessage

logger = logging.getLogger(__name__)


class OpenAIClient(ILLMClient):
    BASE_URL = "https://api.openai.com/v1/chat/completions"
    DEFAULT_SALES_ANALYSIS_MODEL = "gpt-4.1"

    def __init__(self, api_key: Optional[str] = None, timeout: int = 200):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.timeout = timeout

        if not self.api_key:
            raise EnvironmentError("Missing environment variable: OPENAI_API_KEY")

    async def send_message(
        self,
        message: str,
        model: str = DEFAULT_SALES_ANALYSIS_MODEL,
        response_format: Optional[dict] = None,
    ) -> Optional[str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "stream": False,
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(self.BASE_URL, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        choices = data.get("choices")
                        if choices and len(choices) > 0:
                            return choices[0]["message"]["content"]
                        logger.warning("Unexpected response structure from OpenAI API.")
                        return None

                    error_text = await response.text()
                    logger.error(f"OpenAI API error {response.status}: {error_text}")
                    return None

        except asyncio.TimeoutError:
            logger.error("OpenAI API request timed out.")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"Network error while calling OpenAI API: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error during OpenAI API call: {e}")
            return None

    async def stream_message(
        self,
        message: str,
        model: str = DEFAULT_SALES_ANALYSIS_MODEL,
        response_format: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        messages: list[ChatMessage] = [{"role": "system", "content": message}]
        async for chunk in self.stream_messages(messages, model=model, response_format=response_format):
            yield chunk

    async def stream_messages(
        self,
        messages: list[ChatMessage],
        model: str = DEFAULT_SALES_ANALYSIS_MODEL,
        response_format: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(self.BASE_URL, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenAI streaming error {response.status}: {error_text}")
                        raise RuntimeError(f"API error {response.status}: {error_text}")

                    async for line in response.content:
                        line = line.decode("utf-8").strip()
                        if not line or line == "[DONE]" or line == "data: [DONE]":
                            continue

                        if line.startswith("data: "):
                            try:
                                chunk = json.loads(line[6:])
                                choices = chunk.get("choices", [])
                                if not choices:
                                    continue

                                delta = choices[0].get("delta", {})
                                content = delta.get("content")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse OpenAI JSON chunk: {line}")
                                continue

        except asyncio.TimeoutError:
            logger.error("OpenAI streaming request timed out.")
            raise RuntimeError("Request timed out")
        except aiohttp.ClientError as e:
            logger.error(f"Network error during OpenAI streaming: {e}")
            raise RuntimeError(f"Network error: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error during OpenAI streaming: {e}")
            raise RuntimeError(f"Streaming error: {e}")

    async def close(self) -> None:
        return None

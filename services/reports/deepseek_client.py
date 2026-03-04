import os
import logging
import aiohttp
import asyncio
import json
from typing import Optional, AsyncGenerator

logger = logging.getLogger(__name__)

class DeepSeekClient:
    """
    Asynchronous client for interacting with the DeepSeek API.

    Handles sending messages to the DeepSeek chat completion endpoint,
    managing authorization, timeouts, and error handling.
    """

    BASE_URL = "https://api.deepseek.com/chat/completions"

    def __init__(self, api_key: Optional[str] = None, timeout: int = 200):
        """
        Initialize the DeepSeekClient.

        Args:
            api_key (Optional[str]): DeepSeek API key. 
                If not provided, it will be fetched from environment variables.
            timeout (int): Maximum wait time for API responses in seconds.
        """
        self.api_key = api_key or os.getenv("DEEP_SEEK_API_KEY")
        self.timeout = timeout

        if not self.api_key:
            raise EnvironmentError("Missing environment variable: DEEP_SEEK_API_KEY")

    async def send_message(
        self,
        message: str,
        model: str = "deepseek-reasoner",
        response_format: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Sends a message to the DeepSeek API and returns the complete model response.
        For streaming responses, use stream_message() instead.

        Args:
            message (str): The input message to send.
            model (str): Model identifier. Defaults to 'deepseek-reasoner'.

        Returns:
            Optional[str]: The complete generated response text or None if an error occurs.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": message}
            ],
            "stream": False
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            # Using aiohttp for non-blocking async HTTP requests
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(self.BASE_URL, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        choices = data.get("choices")
                        if choices and len(choices) > 0:
                            return choices[0]["message"]["content"]
                        else:
                            logger.warning("Unexpected response structure from DeepSeek API.")
                            return None
                    else:
                        # Log detailed error message
                        error_text = await response.text()
                        logger.error(f"DeepSeek API error {response.status}: {error_text}")
                        return None

        except asyncio.TimeoutError:
            logger.error("DeepSeek API request timed out.")
            return None

        except aiohttp.ClientError as e:
            logger.error(f"Network error while calling DeepSeek API: {e}")
            return None

        except Exception as e:
            logger.exception(f"Unexpected error during DeepSeek API call: {e}")
            return None

    async def stream_message(
        self,
        message: str,
        model: str = "deepseek-reasoner",
        response_format: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streams a message to the DeepSeek API and yields response chunks progressively.
        
        Args:
            message (str): The input message to send.
            model (str): Model identifier. Defaults to 'deepseek-reasoner'.
            
        Yields:
            str: Text chunks as they arrive from the API.
            
        Raises:
            RuntimeError: If the API response is invalid or streaming fails.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": message}
            ],
            "stream": True
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(self.BASE_URL, headers=headers, json=payload) as response:
                    if response.status == 200:
                        # Read streaming response line by line
                        async for line in response.content:
                            line = line.decode('utf-8').strip()
                            
                            # Skip empty lines and [DONE] signals
                            if not line or line == "[DONE]":
                                continue
                            
                            # Parse SSE format: "data: {...}"
                            if line.startswith("data: "):
                                try:
                                    json_str = line[6:]  # Remove "data: " prefix
                                    chunk = json.loads(json_str)
                                    
                                    # Extract content from choices[0].delta.content
                                    choices = chunk.get("choices", [])
                                    if choices and len(choices) > 0:
                                        delta = choices[0].get("delta", {})
                                        content = delta.get("content")
                                        if content:
                                            yield content
                                            
                                except json.JSONDecodeError:
                                    logger.warning(f"Failed to parse JSON chunk: {line}")
                                    continue
                    else:
                        error_text = await response.text()
                        logger.error(f"DeepSeek streaming error {response.status}: {error_text}")
                        raise RuntimeError(f"API error {response.status}: {error_text}")

        except asyncio.TimeoutError:
            logger.error("DeepSeek streaming request timed out.")
            raise RuntimeError("Request timed out")

        except aiohttp.ClientError as e:
            logger.error(f"Network error during streaming: {e}")
            raise RuntimeError(f"Network error: {e}")

        except Exception as e:
            logger.exception(f"Unexpected error during streaming: {e}")
            raise RuntimeError(f"Streaming error: {e}")

    async def stream_messages(
        self,
        messages: list[dict],
        model: str = "deepseek-reasoner",
        response_format: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streams a list of messages to the DeepSeek API and yields response chunks progressively.
        Args:
            messages (list[dict]): List of message dicts with 'role' and 'content'.
            model (str): Model identifier. Defaults to 'deepseek-reasoner'.
        Yields:
            str: Text chunks as they arrive from the API.
        Raises:
            RuntimeError: If the API response is invalid or streaming fails.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "stream": True
        }
        if response_format:
            payload["response_format"] = response_format
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(self.BASE_URL, headers=headers, json=payload) as response:
                    if response.status == 200:
                        async for line in response.content:
                            line = line.decode('utf-8').strip()
                            if not line or line == "[DONE]":
                                continue
                            if line.startswith("data: "):
                                try:
                                    json_str = line[6:]
                                    chunk = json.loads(json_str)
                                    choices = chunk.get("choices", [])
                                    if choices and len(choices) > 0:
                                        delta = choices[0].get("delta", {})
                                        content = delta.get("content")
                                        if content:
                                            yield content
                                except json.JSONDecodeError:
                                    logger.warning(f"Failed to parse JSON chunk: {line}")
                                    continue
                    else:
                        error_text = await response.text()
                        logger.error(f"DeepSeek streaming error {response.status}: {error_text}")
                        raise RuntimeError(f"API error {response.status}: {error_text}")
        except asyncio.TimeoutError:
            logger.error("DeepSeek streaming request timed out.")
            raise RuntimeError("Request timed out")
        except aiohttp.ClientError as e:
            logger.error(f"Network error during streaming: {e}")
            raise RuntimeError(f"Network error: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error during streaming: {e}")
            raise RuntimeError(f"Streaming error: {e}")
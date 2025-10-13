import os
import logging
import aiohttp
import asyncio
from typing import Optional

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

    async def send_message(self, message: str, model: str = "deepseek-reasoner") -> Optional[str]:
        """
        Sends a message to the DeepSeek API and returns the model response.

        Args:
            message (str): The input message to send.
            model (str): Model identifier. Defaults to 'deepseek-reasoner'.

        Returns:
            Optional[str]: The generated response text or None if an error occurs.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": message}
            ]
        }

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
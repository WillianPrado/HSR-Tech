import aiohttp
from typing import Any, Dict, Optional, Union
from tenacity import retry, stop_after_attempt, wait_exponential
from fastapi import HTTPException

class AsyncHTTPClient:
    def __init__(self):
        self.session = aiohttp.ClientSession()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def post(
        self,
        url: str,
        headers: Dict[str, str],
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> Union[Dict[str, Any], str]:
        try:
            # Se "files" for fornecido, use aiohttp.FormData para construir o corpo da requisição
            if files:
                form_data = aiohttp.FormData()
                for field, file in files.items():
                    form_data.add_field(field, file, filename=file.name, content_type="application/octet-stream")
                # Adiciona os dados adicionais no FormData
                if data:
                    for key, value in data.items():
                        form_data.add_field(key, value)

                # Se o cabeçalho Content-Type não foi fornecido, o aiohttp cuidará dele automaticamente.
                headers["Content-Type"] = f"multipart/form-data; boundary={form_data.boundary}"
                async with self.session.post(url, headers=headers, data=form_data, timeout=timeout) as response:
                    response.raise_for_status()
                    return await response.json()
            else:
                # Se não há arquivos, realiza o envio normalmente com json ou data
                async with self.session.post(url, headers=headers, json=json, data=data, timeout=timeout) as response:
                    response.raise_for_status()
                    return await response.json()
        except aiohttp.ContentTypeError:
            return await response.text()
        except Exception as e:
            raise HTTPException(500, f"HTTP request failed: {str(e)}")

    async def close(self):
        await self.session.close()

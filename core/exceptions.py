from fastapi import HTTPException, status

class InvalidZipError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Erro no arquivo ZIP: {detail}"
        )
from fastapi import Request
from fastapi.responses import JSONResponse
from .exceptions import AppException

async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "message": exc.detail
            }
        },
    )

from typing import Literal

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/health", tags=["Health"])


class LivenessResponse(BaseModel):
    status: Literal["ok"]


@router.get("/livez", response_model=LivenessResponse)
async def livez() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=LivenessResponse(status="ok").model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )

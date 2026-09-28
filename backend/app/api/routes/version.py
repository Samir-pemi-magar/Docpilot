from typing import Annotated
from fastapi import APIRouter, Depends
from app.core.config import Settings,get_settings
from app.schemas.version import VersionResponse

router = APIRouter()

@router.get("/version", response_model = VersionResponse)
async def get_version(
    settings: Annotated[Settings, Depends(get_settings)],
) ->VersionResponse:
    return VersionResponse(
        app_name = settings.app_name,
        version = settings.app_version,
        environment = settings.environment
    )

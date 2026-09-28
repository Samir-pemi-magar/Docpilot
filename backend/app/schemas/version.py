from pydantic import BaseModel

class VersionResponse(BaseModel):
    app_name: str
    version: str
    environment: str
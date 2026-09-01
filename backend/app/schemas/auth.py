from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserMe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    roles: list[str]
    is_active: bool

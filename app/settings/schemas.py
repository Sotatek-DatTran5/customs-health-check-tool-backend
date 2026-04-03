from pydantic import BaseModel


class ProfileResponse(BaseModel):
    full_name: str
    email: str
    role: str
    username: str

    class Config:
        from_attributes = True


class EmailConfigResponse(BaseModel):
    smtp_host: str
    smtp_port: int
    sender_email: str
    sender_name: str
    smtp_username: str
    smtp_password: str
    is_enabled: bool

    class Config:
        from_attributes = True


class EmailConfigUpdate(BaseModel):
    smtp_host: str
    smtp_port: int
    sender_email: str
    sender_name: str
    smtp_username: str
    smtp_password: str
    is_enabled: bool = False

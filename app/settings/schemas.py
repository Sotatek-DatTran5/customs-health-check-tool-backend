from pydantic import BaseModel


class ProfileResponse(BaseModel):
    full_name: str
    email: str
    role: str
    username: str | None = None
    locale: str = "vi"
    company_name: str | None = None
    tax_code: str | None = None
    company_address: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    contact_email: str | None = None
    industry: str | None = None
    company_type: str | None = None
    is_first_login: bool = False

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    username: str | None = None
    company_name: str | None = None
    tax_code: str | None = None
    company_address: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    contact_email: str | None = None
    industry: str | None = None
    company_type: str | None = None


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

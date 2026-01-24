from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class DeviceRegister(BaseModel):
    device_id: str
    device_name: str
    fcm_token: Optional[str] = None

class DeviceBase(BaseModel):
    device_id: str
    device_name: str

class DeviceResponse(DeviceBase):
    id: str
    tenant_id: str
    is_approved: bool
    is_enabled: bool
    last_seen_at: datetime
    created_at: datetime
    user_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class MobileLoginRequest(BaseModel):
    username: str
    password: str
    device_id: str  # Mandatory for mobile login
    device_name: str

class MobileLoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    device_status: DeviceResponse

class ToggleApprovalRequest(BaseModel):
    is_approved: bool

class ToggleEnabledRequest(BaseModel):
    is_enabled: bool

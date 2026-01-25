from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.modules.auth import models as auth_models
from backend.app.modules.auth import security, services as auth_services
from backend.app.modules.auth.dependencies import get_current_user
from backend.app.modules.ingestion import models as ingestion_models
from backend.app.modules.mobile import schemas

router = APIRouter(tags=["Mobile"])

# --- Mobile App Endpoints (API/V1/MOBILE) ---

@router.post("/login", response_model=schemas.MobileLoginResponse)
def mobile_login(
    payload: schemas.MobileLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Mobile-specific login. Authenticates user AND registers device.
    Returns a Long-Lived JWT (e.g. 30 days).
    """
    # 1. Authenticate User
    user = auth_services.AuthService.authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 2. Register/Update Device
    device = db.query(ingestion_models.MobileDevice).filter(
        ingestion_models.MobileDevice.device_id == payload.device_id,
        ingestion_models.MobileDevice.tenant_id == str(user.tenant_id)
    ).first()
    
    if not device:
        device = ingestion_models.MobileDevice(
            tenant_id=str(user.tenant_id),
            device_id=payload.device_id,
            device_name=payload.device_name,
            is_approved=False, # Default to unapproved
            is_enabled=True,
            user_id=str(user.id)
        )
        db.add(device)
    else:
        # Update name and seen time
        device.device_name = payload.device_name
        device.last_seen_at = datetime.utcnow()
        
    db.commit()
    db.refresh(device)
    
    # 3. Issue Long-Lived Token
    # Using 30 days for mobile convenience
    access_token_expires = timedelta(days=30) 
    access_token = security.create_access_token(
        data={"sub": user.email, "tenant_id": str(user.tenant_id), "device_id": device.device_id},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "expires_in": int(access_token_expires.total_seconds()),
        "device_status": device
    }

@router.post("/register-device", response_model=schemas.DeviceResponse)
def register_device_manually(
    payload: schemas.DeviceRegister,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually register a device if key rotation or re-install happens without full login.
    """
    device = db.query(ingestion_models.MobileDevice).filter(
        ingestion_models.MobileDevice.device_id == payload.device_id,
        ingestion_models.MobileDevice.tenant_id == str(current_user.tenant_id)
    ).first()
    
    if not device:
        device = ingestion_models.MobileDevice(
            tenant_id=str(current_user.tenant_id),
            device_id=payload.device_id,
            device_name=payload.device_name,
            fcm_token=payload.fcm_token,
            is_approved=False,
            user_id=str(current_user.id)
        )
        db.add(device)
    else:
        device.device_name = payload.device_name
        if payload.fcm_token:
            device.fcm_token = payload.fcm_token
        device.last_seen_at = datetime.utcnow()
        
    db.commit()
    db.refresh(device)
    return device

@router.get("/status", response_model=schemas.DeviceResponse)
def check_device_status(
    device_id: str,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Heartbeat endpoint for mobile app to check if it's still approved.
    """
    device = db.query(ingestion_models.MobileDevice).filter(
        ingestion_models.MobileDevice.device_id == device_id,
        ingestion_models.MobileDevice.tenant_id == str(current_user.tenant_id)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    return device

@router.post("/heartbeat", response_model=schemas.DeviceResponse)
def device_heartbeat(
    device_id: str,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Explicit heartbeat to update last_seen_at.
    """
    device = db.query(ingestion_models.MobileDevice).filter(
        (ingestion_models.MobileDevice.id == device_id) | (ingestion_models.MobileDevice.device_id == device_id),
        ingestion_models.MobileDevice.tenant_id == str(current_user.tenant_id)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    device.last_seen_at = datetime.utcnow()
    db.commit()
    db.refresh(device)
    return device

# --- Web Dashboard Management Endpoints (also under /mobile namespace) ---

@router.get("/devices", response_model=List[schemas.DeviceResponse])
def list_devices(
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all registered devices for the tenant (for Web UI).
    """
    return db.query(ingestion_models.MobileDevice).filter(
        ingestion_models.MobileDevice.tenant_id == str(current_user.tenant_id)
    ).order_by(ingestion_models.MobileDevice.last_seen_at.desc()).all()

@router.patch("/devices/{device_id}/approve", response_model=schemas.DeviceResponse)
def approve_device(
    device_id: str,
    payload: schemas.ToggleApprovalRequest,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Toggle device approval status (Web UI only).
    """
    # Authorization check: Only parents can approve? For now, any adult user.
    if current_user.role == "CHILD":
        raise HTTPException(status_code=403, detail="Only adults can manage devices")

    device = db.query(ingestion_models.MobileDevice).filter(
        ingestion_models.MobileDevice.id == device_id,
        ingestion_models.MobileDevice.tenant_id == str(current_user.tenant_id)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    device.is_approved = payload.is_approved
    db.commit()
    db.refresh(device)
    return device

@router.delete("/devices/{device_id}")
def delete_device(
    device_id: str,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Remove/Reject a device.
    """
    if current_user.role == "CHILD":
       # Optional: Allow user to delete their own device by device_id matching?
       # For now, strict role check or ownership check
       pass

    # Find device by ID or Device_ID (Hybrid lookup for convenience)
    device = db.query(ingestion_models.MobileDevice).filter(
        (ingestion_models.MobileDevice.id == device_id) | (ingestion_models.MobileDevice.device_id == device_id),
        ingestion_models.MobileDevice.tenant_id == str(current_user.tenant_id)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    db.delete(device)
    db.commit()
    return {"status": "deleted"}

@router.patch("/devices/{device_id}", response_model=schemas.DeviceResponse)
def update_device(
    device_id: str,
    payload: schemas.DeviceUpdate,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update device metadata (Name, User Assignment, etc).
    """
    device = db.query(ingestion_models.MobileDevice).filter(
        (ingestion_models.MobileDevice.id == device_id) | (ingestion_models.MobileDevice.device_id == device_id),
        ingestion_models.MobileDevice.tenant_id == str(current_user.tenant_id)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    if payload.device_name is not None:
        device.device_name = payload.device_name
    if payload.is_enabled is not None:
        device.is_enabled = payload.is_enabled
    if payload.is_ignored is not None:
        device.is_ignored = payload.is_ignored
    if payload.user_id is not None:
        device.user_id = payload.user_id
        
    db.commit()
    db.refresh(device)
    return device

@router.patch("/devices/{device_id}/enable")
def toggle_device_enabled(
    device_id: str,
    enabled: bool,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Enable or Disable ingestion for a device without removing it.
    """
    device = db.query(ingestion_models.MobileDevice).filter(
        (ingestion_models.MobileDevice.id == device_id) | (ingestion_models.MobileDevice.device_id == device_id),
        ingestion_models.MobileDevice.tenant_id == str(current_user.tenant_id)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    device.is_enabled = enabled
    db.commit()
    db.refresh(device)
    device.is_enabled = enabled
    db.commit()
    db.refresh(device)
    return device

@router.patch("/devices/{device_id}/ignore")
def toggle_device_ignored(
    device_id: str,
    ignored: bool,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mark a device as ignored (soft reject) or restore it.
    """
    device = db.query(ingestion_models.MobileDevice).filter(
        (ingestion_models.MobileDevice.id == device_id) | (ingestion_models.MobileDevice.device_id == device_id),
        ingestion_models.MobileDevice.tenant_id == str(current_user.tenant_id)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    device.is_ignored = ignored
    if ignored:
        device.is_approved = False # Auto-revoke approval if ignored
        

    db.commit()
    db.refresh(device)
    return device

@router.patch("/devices/{device_id}/assign")
def assign_device_user(
    device_id: str,
    payload: schemas.AssignUserRequest,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Assign a device to a specific family member/user.
    """
    if current_user.role == "CHILD":
        raise HTTPException(status_code=403, detail="Only adults can manage devices")

    device = db.query(ingestion_models.MobileDevice).filter(
        (ingestion_models.MobileDevice.id == device_id) | (ingestion_models.MobileDevice.device_id == device_id),
        ingestion_models.MobileDevice.tenant_id == str(current_user.tenant_id)
    ).first()
    
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    device.user_id = payload.user_id
    db.commit()
    db.refresh(device)
    return device

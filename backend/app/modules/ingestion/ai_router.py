from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel
from backend.app.core.database import get_db
from backend.app.modules.auth import models as auth_models
from backend.app.modules.auth.dependencies import get_current_user
from backend.app.modules.ingestion import models as ingestion_models
import json

router = APIRouter(prefix="/ai", tags=["AI Settings"])

class AISettingsUpdate(BaseModel):
    provider: str
    model_name: str
    api_key: Optional[str] = None
    is_enabled: bool
    prompts: Dict[str, str]

class AISettingsRead(BaseModel):
    provider: str
    model_name: str
    is_enabled: bool
    prompts: Dict[str, str]
    has_api_key: bool

@router.get("/settings", response_model=AISettingsRead)
def get_ai_settings(
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    config = db.query(ingestion_models.AIConfiguration).filter(
        ingestion_models.AIConfiguration.tenant_id == str(current_user.tenant_id)
    ).first()

    if not config:
        # Return defaults
        return {
            "provider": "gemini",
            "model_name": "gemini-pro",
            "is_enabled": False,
            "prompts": {
                "parsing": "Extract transaction details from the following message. Return JSON with: amount (number), date (DD/MM/YYYY), recipient (string), account_mask (4 digits), ref_id (string or null), type (DEBIT/CREDIT)."
            },
            "has_api_key": False
        }

    return {
        "provider": config.provider,
        "model_name": config.model_name,
        "is_enabled": config.is_enabled,
        "prompts": json.loads(config.prompts_json or "{}"),
        "has_api_key": bool(config.api_key)
    }

@router.post("/settings")
def update_ai_settings(
    payload: AISettingsUpdate,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    config = db.query(ingestion_models.AIConfiguration).filter(
        ingestion_models.AIConfiguration.tenant_id == str(current_user.tenant_id)
    ).first()

    if not config:
        config = ingestion_models.AIConfiguration(
            tenant_id=str(current_user.tenant_id)
        )
        db.add(config)

    config.provider = payload.provider
    config.model_name = payload.model_name
    config.is_enabled = payload.is_enabled
    config.prompts_json = json.dumps(payload.prompts)
    
    if payload.api_key:
        config.api_key = payload.api_key

    db.commit()
    return {"status": "updated"}

@router.post("/test")
def test_ai_connection(
    payload: Dict[str, str],
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from backend.app.modules.ingestion.ai_service import AIService
    content = payload.get("content", "Test transaction: Spent Rs 500 at Amazon using card XX1234 on 01/01/2024")
    
    try:
        res = AIService.parse_with_ai(db, str(current_user.tenant_id), content)
        if res:
            return {"status": "success", "data": res.dict()}
        return {"status": "failed", "message": "AI returned no result. Check API key and configuration."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/models")
def list_ai_models(
    provider: str = "gemini",
    api_key: Optional[str] = None,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from backend.app.modules.ingestion.ai_service import AIService
    return AIService.list_available_models(db, str(current_user.tenant_id), provider, api_key)

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.modules.auth import models as auth_models
from backend.app.modules.auth.dependencies import get_current_user
from backend.app.modules.finance.services.analytics_service import AnalyticsService

router = APIRouter()

@router.get("/metrics")
def get_metrics(
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return AnalyticsService.get_summary_metrics(db, str(current_user.tenant_id), user_role=current_user.role)

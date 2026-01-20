from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from backend.app.core.database import get_db
from backend.app.modules.auth import models as auth_models
from backend.app.modules.auth.dependencies import get_current_user
from backend.app.modules.finance.services.mutual_funds import MutualFundService
from backend.app.modules.ingestion.cas_parser import CASParser
from backend.app.modules.finance import models as finance_models
from fastapi import UploadFile, File, Form
import shutil
import tempfile
import os
router = APIRouter(prefix="/mutual-funds", tags=["Mutual Funds"])

class TransactionCreate(BaseModel):
    scheme_code: str
    type: str = "BUY" # BUY, SELL
    amount: float
    units: float
    nav: float
    date: datetime
    folio_number: Optional[str] = None

@router.get("/search")
def search_funds(q: str = Query(..., min_length=2)):
    return MutualFundService.search_funds(q)

@router.get("/{scheme_code}/nav")
def get_nav(scheme_code: str):
    data = MutualFundService.get_fund_nav(scheme_code)
    if not data:
        raise HTTPException(status_code=404, detail="Scheme not found or API error")
    
    # Extract latest NAV
    if data and data.get("data"):
        latest = data["data"][0] # API returns sorted by date desc
        return {"nav": float(latest["nav"]), "date": latest["date"]}
    
    raise HTTPException(status_code=404, detail="NAV data unavailable")

@router.get("/portfolio")
def get_portfolio(
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return MutualFundService.get_portfolio(db, str(current_user.tenant_id))

@router.post("/transaction")
def add_transaction(
    payload: TransactionCreate,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        data = payload.dict()
        order = MutualFundService.add_transaction(db, str(current_user.tenant_id), data)
        return {"status": "success", "order_id": order.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
@router.post("/import-cas")
def import_cas_pdf(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            shutil.copyfileobj(file.file, f)
            temp_path = f.name
            
        transactions = CASParser.parse_pdf(temp_path, password)
        
        processed_count = 0
        for txn in transactions:
            # Auto-map scheme
            results = MutualFundService.search_funds(txn['scheme_name'])
            if results:
                txn['scheme_code'] = results[0]['schemeCode'] # Naive match
                MutualFundService.add_transaction(db, str(current_user.tenant_id), txn)
                processed_count += 1
                
        return {"status": "success", "processed": processed_count, "found": len(transactions)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path:
            os.remove(temp_path)

@router.post("/import-cas-email")
def trigger_cas_email_import(
    password: str = Form(...),
    email_config_id: Optional[str] = Form(None),
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Find email config
    query = db.query(finance_models.EmailConfiguration).filter(
        finance_models.EmailConfiguration.tenant_id == str(current_user.tenant_id)
    )
    if email_config_id:
        query = query.filter(finance_models.EmailConfiguration.id == email_config_id)
    
    config = query.first()
    if not config:
        raise HTTPException(status_code=404, detail="No email configuration found")
        
    stats = CASParser.find_and_process_cas_emails(db, str(current_user.tenant_id), config, password)
    return {"status": "completed", "stats": stats}

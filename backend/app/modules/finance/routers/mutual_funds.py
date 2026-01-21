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
def search_funds(
    q: Optional[str] = Query(None, min_length=2),
    category: Optional[str] = Query(None),
    amc: Optional[str] = Query(None),
    limit: int = 20,
    offset: int = 0,
    sort_by: str = Query('relevance')
):
    if not any([q, category, amc]):
        raise HTTPException(status_code=400, detail="Search query or filter required")
    return MutualFundService.search_funds(query=q, category=category, amc=amc, limit=limit, offset=offset, sort_by=sort_by)

@router.get("/indices")
def get_market_indices():
    return MutualFundService.get_market_indices()

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

@router.get("/analytics")
def get_analytics(
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return MutualFundService.get_portfolio_analytics(db, str(current_user.tenant_id))

@router.get("/analytics/performance-timeline")
def get_performance_timeline(
    period: str = "1y",
    granularity: str = "1w",
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get portfolio performance timeline.
    
    Query params:
    - period: One of '1m', '3m', '6m', '1y', 'all'
    - granularity: One of '1d', '1w', '1m'
    """
    return MutualFundService.get_performance_timeline(db, str(current_user.tenant_id), period, granularity)

@router.delete("/analytics/cache")
def clear_timeline_cache(
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear timeline cache for current user"""
    count = MutualFundService.clear_timeline_cache(db, str(current_user.tenant_id))
    return {"message": f"Cleared {count} cache entries"}

@router.post("/cleanup-duplicates")
def cleanup_duplicate_orders(
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove duplicate mutual fund orders that might have been imported multiple times"""
    from backend.app.modules.finance.models import MutualFundOrder, MutualFundHolding
    from sqlalchemy import func
    
    tenant_id = str(current_user.tenant_id)
    
    # 1. Find duplicate groups
    duplicates = db.query(
        MutualFundOrder.scheme_code, 
        MutualFundOrder.order_date, 
        MutualFundOrder.units, 
        MutualFundOrder.amount, 
        MutualFundOrder.type
    ).filter(MutualFundOrder.tenant_id == tenant_id).group_by(
        MutualFundOrder.scheme_code, 
        MutualFundOrder.order_date, 
        MutualFundOrder.units, 
        MutualFundOrder.amount, 
        MutualFundOrder.type
    ).having(func.count('*') > 1).all()
    
    removed_count = 0
    for sc, d, u, a, t in duplicates:
        # Keep the first one, delete the rest
        all_matches = db.query(MutualFundOrder).filter(
            MutualFundOrder.tenant_id == tenant_id,
            MutualFundOrder.scheme_code == sc,
            MutualFundOrder.order_date == d,
            MutualFundOrder.units == u,
            MutualFundOrder.amount == a,
            MutualFundOrder.type == t
        ).order_by(MutualFundOrder.created_at).all()
        
        # Keep first, delete others
        to_delete = all_matches[1:]
        for order in to_delete:
            db.delete(order)
            removed_count += 1
            
    db.commit()
    
    # 2. Recalculate holdings (since units were double/triple counted)
    # This is a bit complex to do fully here, but we can reset units to 0 and re-add?
    # Better: just clear holdings and let the next calculation/fetch handle it if we have a way
    # Or just tell user to re-import? No, let's fix it properly.
    
    holdings = db.query(MutualFundHolding).filter(MutualFundHolding.tenant_id == tenant_id).all()
    for holding in holdings:
        # Reset units and avg price
        orders = db.query(MutualFundOrder).filter(
            MutualFundOrder.tenant_id == tenant_id,
            MutualFundOrder.scheme_code == holding.scheme_code
        ).all()
        
        total_units = 0
        total_cost = 0
        for o in orders:
            if o.type == "BUY":
                total_units += float(o.units)
                total_cost += float(o.amount)
            else:
                total_units -= float(o.units)
                # Simple avg cost reduction for sell
        
        holding.units = max(0, total_units)
        holding.average_price = total_cost / total_units if total_units > 0 else 0
        holding.current_value = float(holding.units) * float(holding.last_nav or 0)
        
    db.commit()
    
    return {"message": f"Removed {removed_count} duplicate orders and synchronized {len(holdings)} holdings"}

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

@router.delete("/holdings/{holding_id}")
def delete_holding(
    holding_id: str,
    current_user: auth_models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        MutualFundService.delete_holding(db, str(current_user.tenant_id), holding_id)
        return {"status": "success", "message": "Holding deleted"}
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
        
        imported = []
        failed = []
        
        # Pre-fetch funds list once to avoid N API calls
        import httpx
        from rapidfuzz import process, fuzz
        
        all_funds_cache = []
        try:
            print("[Import CAS] Fetching master fund list...")
            resp = httpx.get("https://api.mfapi.in/mf")
            if resp.status_code == 200:
                all_funds_cache = resp.json()
                print(f"[Import CAS] Master list fetched: {len(all_funds_cache)} schemes.")
        except Exception as e:
            print(f"[Import CAS] Failed to fetch master list: {e}")

        # Map scheme codes for O(1) AMFI lookup
        amfi_map = {str(f['schemeCode']): f for f in all_funds_cache}
        scheme_names = [f['schemeName'] for f in all_funds_cache]

        for i, txn in enumerate(transactions):
            matched_scheme = None
            failure_reason = None
            
            # ONLY use AMFI Code (Definitive Identifier)
            # CAS files from CAMS/KFintech ALWAYS include AMFI codes
            amfi_code = txn.get('amfi')
            
            if not amfi_code:
                failure_reason = "AMFI code missing in CAS data"
            elif str(amfi_code) in amfi_map:
                matched_scheme = amfi_map[str(amfi_code)]
            else:
                failure_reason = f"AMFI code {amfi_code} not found in master fund list (possibly delisted/merged fund)"
            
            if matched_scheme:
                txn['scheme_code'] = matched_scheme['schemeCode'] 
                txn['mapped_name'] = matched_scheme['schemeName']
                try:
                    MutualFundService.add_transaction(db, str(current_user.tenant_id), txn)
                    imported.append(txn)
                except Exception as e:
                    txn['error'] = f"Database error: {str(e)}"
                    failed.append(txn)
            else:
                txn['error'] = failure_reason or "Unknown mapping error"
                failed.append(txn)
                
        return {
            "status": "success", 
            "processed": len(imported), 
            "total_found": len(transactions),
            "details": {
                "imported": imported,
                "failed": failed
            }
        }
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

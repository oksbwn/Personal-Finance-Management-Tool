import httpx
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
from backend.app.modules.finance import models as finance_models
from backend.app.modules.finance.models import MutualFundsMeta, MutualFundHolding, MutualFundOrder

MFAPI_BASE_URL = "https://api.mfapi.in/mf"

class MutualFundService:
    
    @staticmethod
    def search_funds(query: str, limit: int = 10):
        # MFAPI doesn't have a search endpoint, it has a large JSON of all funds.
        # For efficiency, we might want to cache this or use a different approach.
        # However, for now, we can try to search against our local 'mutual_funds_meta' if populated, 
        # or fetch the list from MFAPI once and cache it.
        # MFAPI List: https://api.mfapi.in/mf
        try:
            # TODO: Implement proper caching or search. 
            # For now, let's assume we search our local DB which we populate on demand or via a script.
            # But the user expects search to work. 
            # Let's fetch the full list (lightweight JSON) and filter in memory for V1, 
            # then eventually move to DB search.
            response = httpx.get(f"{MFAPI_BASE_URL}")
            if response.status_code == 200:
                all_funds = response.json()
                # Simple case-insensitive search
                results = [
                    f for f in all_funds 
                    if query.lower() in f.get('schemeName', '').lower()
                ]
                return results[:limit]
            return []
        except Exception as e:
            print(f"Error searching funds: {e}")
            return []

    @staticmethod
    def get_fund_nav(scheme_code: str):
        try:
            response = httpx.get(f"{MFAPI_BASE_URL}/{scheme_code}")
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "SUCCESS":
                    # Meta: fund_house, scheme_type, scheme_category, scheme_code, scheme_name
                    # Data: date, nav
                    return data
            return None
        except Exception as e:
            print(f"Error fetching NAV: {e}")
            return None

    @staticmethod
    def add_transaction(db: Session, tenant_id: str, data: dict):
        # 1. Ensure Meta exists
        scheme_code = data['scheme_code']
        meta = db.query(MutualFundsMeta).filter(MutualFundsMeta.scheme_code == scheme_code).first()
        
        if not meta:
            # Fetch from API and save
            fund_data = MutualFundService.get_fund_nav(scheme_code)
            if fund_data:
                meta_info = fund_data.get("meta", {})
                meta = MutualFundsMeta(
                    scheme_code=str(meta_info.get("scheme_code")),
                    scheme_name=meta_info.get("scheme_name"),
                    fund_house=meta_info.get("fund_house"),
                    category=meta_info.get("scheme_category")
                )
                db.add(meta)
                db.commit()
            else:
                raise ValueError("Invalid Scheme Code or API Error")

        # 2. Create Order
        order = MutualFundOrder(
            tenant_id=tenant_id,
            scheme_code=scheme_code,
            type=data.get('type', 'BUY'),
            amount=data['amount'],
            units=data['units'],
            nav=data['nav'],
            order_date=data['date'],
            import_source="MANUAL"
        )
        db.add(order)
        
        # 3. Update/Create Holding
        holding = db.query(MutualFundHolding).filter(
            MutualFundHolding.tenant_id == tenant_id,
            MutualFundHolding.scheme_code == scheme_code
        ).first()

        if not holding:
            holding = MutualFundHolding(
                tenant_id=tenant_id,
                scheme_code=scheme_code,
                folio_number=data.get('folio_number')
            )
            db.add(holding)
        
        # Update Holding Logic (Weighted Average Price for BUY, FIFO/Avg for SELL - keeping simple Avg for now)
        if order.type == "BUY":
            total_cost = (holding.average_price * holding.units) + (order.nav * order.units)
            total_units = holding.units + order.units
            holding.average_price = total_cost / total_units if total_units > 0 else 0
            holding.units = total_units
        elif order.type == "SELL":
            # Simplify: Reduce units, keep avg price same (standard accounting)
            holding.units = holding.units - order.units
        
        # Update current value based on latest NAV (which is this order's NAV presumably, or fetch latest)
        holding.last_nav = order.nav
        holding.current_value = holding.units * holding.last_nav
        holding.last_updated_at = datetime.utcnow()

        order.holding_id = holding.id
        db.commit()
        return order

    @staticmethod
    def get_portfolio(db: Session, tenant_id: str):
        holdings = db.query(MutualFundHolding).filter(MutualFundHolding.tenant_id == tenant_id).all()
        # Enrich with Meta name
        results = []
        for h in holdings:
            meta = db.query(MutualFundsMeta).filter(MutualFundsMeta.scheme_code == h.scheme_code).first()
            results.append({
                "id": h.id,
                "scheme_code": h.scheme_code,
                "scheme_name": meta.scheme_name if meta else "Unknown Fund",
                "units": float(h.units),
                "average_price": float(h.average_price),
                "current_value": float(h.current_value) if h.current_value else 0,
                "invested_value": float(h.units * h.average_price),
                "last_nav": float(h.last_nav) if h.last_nav else 0,
                "profit_loss": float(h.current_value - (h.units * h.average_price)) if h.current_value else 0
            })
        return results

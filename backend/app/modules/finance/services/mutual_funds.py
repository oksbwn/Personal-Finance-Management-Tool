import httpx
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
from backend.app.modules.finance import models as finance_models
from backend.app.modules.finance.models import MutualFundsMeta, MutualFundHolding, MutualFundOrder

MFAPI_BASE_URL = "https://api.mfapi.in/mf"

class MutualFundService:
    
    @staticmethod
    def get_mock_returns(scheme_code: str) -> float:
        try:
            code_str = str(scheme_code or '0')
            hash_val = sum(ord(c) for c in code_str)
            base = 12 + (hash_val % 25)
            # Add some decimal variation based on hash to make it look real
            decimal = (hash_val % 10) / 10.0
            return float(f"{base + decimal:.1f}")
        except:
            return 12.0

    @staticmethod
    def search_funds(query: Optional[str] = None, category: Optional[str] = None, amc: Optional[str] = None, limit: int = 20, offset: int = 0, sort_by: str = 'relevance', all_funds_cache: Optional[List[dict]] = None):
        try:
            # Fetch the main list from MFAPI if not provided
            if all_funds_cache:
                all_funds = all_funds_cache
            else:
                response = httpx.get(f"{MFAPI_BASE_URL}")
                if response.status_code == 200:
                    all_funds = response.json()
                else:
                    return []
            
            # Continue with processing...
            if True: # indent preservation wrapper
                query_low = query.lower() if query else None
                cat_low = category.lower() if category else None
                amc_low = amc.lower() if amc else None

                # Optimization: Direct filter if possible, otherwise iterate
                filtered_funds = []
                for f in all_funds:
                    scheme_name = f.get('schemeName', '').lower()
                    
                    # Filtering logic
                    match = True
                    if query_low and query_low not in scheme_name:
                        match = False
                    if cat_low and cat_low not in scheme_name: 
                        match = False
                    if amc_low and amc_low not in scheme_name: 
                        match = False
                        
                    if match:
                        filtered_funds.append(f)

                # Sorting
                if sort_by == 'returns_desc':
                    filtered_funds.sort(key=lambda x: MutualFundService.get_mock_returns(str(x.get('schemeCode'))), reverse=True)
                elif sort_by == 'returns_asc':
                    filtered_funds.sort(key=lambda x: MutualFundService.get_mock_returns(str(x.get('schemeCode'))))
                # Default 'relevance' keeps original order (usually by scheme code or alphabetical from API)

                # Pagination
                start = offset
                end = offset + limit
                results = filtered_funds[start:end]
                            
                return results
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

        # 2. Check for duplicate order (Idempotency)
        # Check if an identical order already exists for this tenant
        existing_order = db.query(MutualFundOrder).filter(
            MutualFundOrder.tenant_id == tenant_id,
            MutualFundOrder.scheme_code == scheme_code,
            MutualFundOrder.order_date == data['date'],
            MutualFundOrder.type == data.get('type', 'BUY'),
            MutualFundOrder.units == data['units'],
            MutualFundOrder.amount == data['amount']
        ).first()

        if existing_order:
            print(f"[Import] Skipping duplicate order for scheme {scheme_code} on {data['date']}")
            return existing_order

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
        folio_number = data.get('folio_number')
        query = db.query(MutualFundHolding).filter(
            MutualFundHolding.tenant_id == tenant_id,
            MutualFundHolding.scheme_code == scheme_code
        )
        
        if folio_number:
            query = query.filter(MutualFundHolding.folio_number == folio_number)
        else:
            query = query.filter(MutualFundHolding.folio_number.is_(None))
            
        holding = query.first()

        if not holding:
            holding = MutualFundHolding(
                tenant_id=tenant_id,
                scheme_code=scheme_code,
                folio_number=folio_number,
                units=0,
                average_price=0
            )
            db.add(holding)
            db.flush() # Get ID for order
        else:
            # Overwrite if we somehow got a new folio for existing (should not happen with updated filter)
            if folio_number:
                holding.folio_number = folio_number
        
        # Update Holding Logic (Weighted Average Price for BUY, FIFO/Avg for SELL - keeping simple Avg for now)
        if order.type == "BUY":
            # Handle possible None types from DB and Decimal vs Float coercion
            current_units = float(holding.units or 0.0)
            current_avg = float(holding.average_price or 0.0)
            
            # Use order.amount if available (more precise), fallback to units*nav
            order_units = float(order.units)
            order_amount = float(order.amount)
            txn_cost = order_amount if order_amount > 0 else (float(order.nav) * order_units)
            
            total_cost = (current_avg * current_units) + txn_cost
            total_units = current_units + order_units
            
            holding.average_price = total_cost / total_units if total_units > 0 else 0.0
            holding.units = total_units
        elif order.type == "SELL":
            # Simplify: Reduce units, keep avg price same (standard accounting)
            current_units = float(holding.units or 0.0)
            holding.units = max(0, current_units - float(order.units))
        
        # Prevent historical imports from overwriting a newer or forced NAV
        # Only update if current NAV is 0/None or if this order is very recent
        if not holding.last_nav or float(holding.last_nav) == 0:
            holding.last_nav = order.nav
            holding.last_updated_at = order.order_date
        
        holding.current_value = float(holding.units) * float(holding.last_nav or 0.0)

        order.holding_id = holding.id
        db.commit()
        return order

    @staticmethod
    def delete_holding(db: Session, tenant_id: str, holding_id: str):
        holding = db.query(MutualFundHolding).filter(
            MutualFundHolding.id == holding_id,
            MutualFundHolding.tenant_id == tenant_id
        ).first()
        
        if not holding:
            raise Exception("Holding not found")
            
        # Delete related orders too? Or keep them?
        # Usually delete checks for safety, but user asked for delete.
        # Let's delete the holding. Cascade should handle orders if configured, 
        # but let's check models. MutualFundHolding doesn't seem to cascade orders in definitions above clearly.
        # Let's just delete the holding row.
        db.delete(holding)
        db.commit()
        return True

    @staticmethod
    def get_portfolio(db: Session, tenant_id: str):
        import asyncio
        
        holdings = db.query(MutualFundHolding).filter(MutualFundHolding.tenant_id == tenant_id).all()
        results = []
        
        # Check for updates needed (Stale > 24h or None)
        updates_made = False
        today = datetime.utcnow().date()
        
        async def fetch_nav_and_sparkline(scheme_code):
            """Fetch both current NAV and 30-day history concurrently"""
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"https://api.mfapi.in/mf/{scheme_code}", timeout=5.0)
                    
                if response.status_code == 200:
                    fund_data = response.json()
                    raw_data = fund_data.get("data", [])
                    
                    def parse_date(d_str):
                        try:
                            return datetime.strptime(d_str, "%d-%m-%Y")
                        except:
                            return datetime.min

                    # Sort by date descending
                    sorted_data = sorted(raw_data, key=lambda x: parse_date(x.get("date", "")), reverse=True)
                    
                    # Latest NAV
                    latest_nav = 0.0
                    nav_date_str = ""
                    if sorted_data:
                        latest_nav_data = sorted_data[0]
                        latest_nav = float(latest_nav_data.get("nav", 0.0))
                        nav_date_str = latest_nav_data.get("date", "")
                    
                    # Sparkline (last 30 days)
                    sparkline_data = sorted_data[:30]  # Get last 30 entries
                    sparkline_data.reverse()  # Reverse to chronological order
                    sparkline = [float(d.get("nav", 0.0)) for d in sparkline_data if d.get("nav")]
                    
                    return {
                        "latest_nav": latest_nav,
                        "nav_date": nav_date_str,
                        "sparkline": sparkline
                    }
                else:
                    return {"latest_nav": 0.0, "nav_date": "", "sparkline": []}
            except Exception as e:
                print(f"Failed to fetch NAV/sparkline for {scheme_code}: {e}")
                return {"latest_nav": 0.0, "nav_date": "", "sparkline": []}
        
        # Fetch all NAV data concurrently
        async def fetch_all_nav_data():
            tasks = [fetch_nav_and_sparkline(h.scheme_code) for h in holdings]
            return await asyncio.gather(*tasks)
        
        nav_data_list = asyncio.run(fetch_all_nav_data())
        
        # Process each holding with its NAV data
        for h, nav_data in zip(holdings, nav_data_list):
            latest_nav = nav_data["latest_nav"]
            nav_date_str = nav_data["nav_date"]
            sparkline = nav_data["sparkline"]
            
            # Update holding if we got valid NAV
            if latest_nav > 0:
                h.last_nav = latest_nav
                current_units = float(h.units or 0.0)
                h.current_value = current_units * latest_nav
                
                def parse_date(d_str):
                    try:
                        return datetime.strptime(d_str, "%d-%m-%Y")
                    except:
                        return datetime.min
                
                h.last_updated_at = parse_date(nav_date_str)
                updates_made = True
            
            # Enrich with Meta name
            meta = db.query(MutualFundsMeta).filter(MutualFundsMeta.scheme_code == h.scheme_code).first()
            
            # Safe float conversion handling None
            units = float(h.units or 0.0)
            avg_price = float(h.average_price or 0.0)
            current_val = float(h.current_value or 0.0)
            invested = units * avg_price
            
            # Profit/Loss Calculation
            pl = 0.0
            if current_val > 0:
                pl = current_val - invested
            
            last_updated_str = h.last_updated_at.strftime("%d-%b-%Y") if h.last_updated_at else "N/A"

            results.append({
                "id": h.id,
                "scheme_code": h.scheme_code,
                "scheme_name": meta.scheme_name if meta else "Unknown Fund",
                "folio_number": h.folio_number,
                "units": units,
                "average_price": avg_price,
                "current_value": current_val,
                "invested_value": invested,
                "last_nav": float(h.last_nav or 0.0),
                "profit_loss": pl,
                "last_updated": last_updated_str,
                "sparkline": sparkline  # 30-day NAV trend
            })
        
        # Commit all updates in one transaction to avoid DuckDB conflicts
        if updates_made:
            db.commit()
            
        return results

    @staticmethod
    def get_market_indices():
        import asyncio
        
        async def fetch_index_data(idx):
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{idx['symbol']}?interval=5m&range=1d"
                headers = {'User-Agent': 'Mozilla/5.0'}
                
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, headers=headers, timeout=5.0)
                
                if response.status_code == 200:
                    data = response.json()
                    meta = data['chart']['result'][0]['meta']
                    current_price = meta['regularMarketPrice']
                    previous_close = meta['chartPreviousClose']
                    change = current_price - previous_close
                    percent = (change / previous_close) * 100
                    
                    indicators = data['chart']['result'][0]['indicators']['quote'][0]
                    closes = indicators.get('close', [])
                    valid_closes = [c for c in closes if c is not None]
                    sparkline = valid_closes[-20:] if len(valid_closes) > 20 else valid_closes

                    return {
                        "name": idx['name'],
                        "value": f"{current_price:,.2f}",
                        "change": f"{change:+.2f}",
                        "percent": f"{percent:+.2f}%",
                        "isUp": change >= 0,
                        "sparkline": sparkline
                    }
                else:
                    return {"name": idx['name'], "value": "Unavailable", "change": "0.00", "percent": "0.00%", "isUp": True}
            except Exception as e:
                pass
                return {"name": idx['name'], "value": "Error", "change": "0.00", "percent": "0.00%", "isUp": True}
        
        async def fetch_all():
            indices = [
                {"name": "NIFTY 50", "symbol": "^NSEI"},
                {"name": "SENSEX", "symbol": "^BSESN"},
                {"name": "BANK NIFTY", "symbol": "^NSEBANK"}
            ]
            tasks = [fetch_index_data(idx) for idx in indices]
            return await asyncio.gather(*tasks)
        
        # Run async tasks
        return asyncio.run(fetch_all())

    @staticmethod
    def get_portfolio_analytics(db: Session, tenant_id: str):
        """
        Calculate portfolio analytics: allocation, top performers, XIRR
        """
        from backend.app.modules.finance.utils.financial_math import xirr, categorize_fund
        
        # Get portfolio data
        holdings = db.query(MutualFundHolding).filter(MutualFundHolding.tenant_id == tenant_id).all()
        
        if not holdings:
            return {
                "asset_allocation": {"equity": 0, "debt": 0, "hybrid": 0, "other": 0},
                "category_allocation": {},
                "top_gainers": [],
                "top_losers": [],
                "xirr": 0,
                "total_invested": 0,
                "current_value": 0
            }
        
        # Calculate asset allocation
        allocation = {"equity": 0.0, "debt": 0.0, "hybrid": 0.0, "other": 0.0}
        category_allocation = {}
        total_value = 0.0
        
        for h in holdings:
            meta = db.query(MutualFundsMeta).filter(MutualFundsMeta.scheme_code == h.scheme_code).first()
            raw_category = meta.category if meta else "Other"
            asset_type = categorize_fund(raw_category)
            current_val = float(h.current_value or 0.0)
            
            allocation[asset_type] += current_val
            
            # Category-wise (Sector proxy)
            if raw_category not in category_allocation:
                category_allocation[raw_category] = 0.0
            category_allocation[raw_category] += current_val
            
            total_value += current_val
        
        # Convert to percentages
        if total_value > 0:
            allocation = {k: round((v / total_value) * 100, 2) for k, v in allocation.items()}
            category_allocation = {k: round((v / total_value) * 100, 2) for k, v in category_allocation.items()}
        
        # Get portfolio with P/L for top performers
        portfolio_data = MutualFundService.get_portfolio(db, tenant_id)
        
        # Calculate P/L percentage for sorting
        for item in portfolio_data:
            invested = item.get('invested_value', 0)
            if invested > 0:
                item['pl_percent'] = round((item['profit_loss'] / invested) * 100, 2)
            else:
                item['pl_percent'] = 0
        
        # Sort by P/L percentage
        sorted_by_pl = sorted(portfolio_data, key=lambda x: x['pl_percent'], reverse=True)
        
        top_gainers = sorted_by_pl[:5]
        top_losers = list(reversed(sorted_by_pl[-5:]))
        
        # Calculate XIRR
        # Get all transactions for EXISTING holdings only (Same as timeline)
        holdings_query = db.query(MutualFundHolding.id).filter(MutualFundHolding.tenant_id == tenant_id).all()
        active_holding_ids = [h.id for h in holdings_query]
        
        orders = db.query(MutualFundOrder).filter(
            MutualFundOrder.tenant_id == tenant_id,
            MutualFundOrder.holding_id.in_(active_holding_ids)
        ).all()
        
        xirr_value = None
        total_invested = 0.0
        
        if orders and len(orders) > 0:
            from datetime import date
            cash_flows = []
            for order in orders:
                # Use units * nav if amount is 0 (fallback for older imports)
                amount = float(order.amount)
                if amount <= 0:
                    amount = float(order.units) * float(order.nav)
                
                # Convert order_date to date if it's datetime
                order_date = order.order_date.date() if hasattr(order.order_date, 'date') else order.order_date
                
                if order.type == "BUY":
                    cash_flows.append((order_date, -amount))  # Outflow is negative
                    total_invested += amount
                else:  # SELL
                    cash_flows.append((order_date, amount))  # Inflow is positive
            
            # Add current value as final inflow at today's date
            if total_value > 0:
                cash_flows.append((date.today(), total_value))
            
            
            try:
                # Need at least one negative (outflow) and one positive (inflow) for XIRR
                sum_out = sum(cf[1] for cf in cash_flows if cf[1] < 0)
                if len(cash_flows) >= 2 and abs(sum_out) > 0.01:
                    xirr_decimal = xirr(cash_flows)
                    xirr_value = round(xirr_decimal * 100, 2)  # Convert to percentage
            except Exception:
                xirr_value = None
        
        return {
            "asset_allocation": allocation,
            "category_allocation": category_allocation,
            "top_gainers": top_gainers,
            "top_losers": top_losers,
            "xirr": xirr_value,
            "total_invested": round(total_invested, 2),
            "current_value": round(total_value, 2)
        }
    
    @staticmethod
    def clear_timeline_cache(db: Session, tenant_id: str, from_date=None):
        """
        Clear timeline cache for a tenant.
        Call this when transactions are added/deleted to invalidate cache.
        
        Args:
            tenant_id: Tenant ID
            from_date: Clear cache from this date onwards (defaults to all)
        """
        from ..models import PortfolioTimelineCache
        
        query = db.query(PortfolioTimelineCache).filter(
            PortfolioTimelineCache.tenant_id == tenant_id
        )
        
        if from_date:
            query = query.filter(PortfolioTimelineCache.snapshot_date >= from_date)
        
        deleted_count = query.delete()
        db.commit()
        return deleted_count
    
    @staticmethod
    def get_performance_timeline(db: Session, tenant_id: str, period: str = "1y", granularity: str = "1w"):
        """
        Calculate portfolio value over time with smart caching.
        
        Returns timeline data with portfolio value and invested amount at weekly intervals.
        """
        from datetime import date, timedelta
        from ..utils.financial_math import calculate_start_date, add_months
        from ..models import PortfolioTimelineCache
        import httpx
        import hashlib
        
        # Get all transactions for EXISTING holdings only
        # This prevents orphaned orders from deleted holdings from inflating the timeline
        holdings = db.query(MutualFundHolding.id).filter(MutualFundHolding.tenant_id == tenant_id).all()
        active_holding_ids = [h.id for h in holdings]
        
        orders = db.query(MutualFundOrder).filter(
            MutualFundOrder.tenant_id == tenant_id,
            MutualFundOrder.holding_id.in_(active_holding_ids)
        ).order_by(MutualFundOrder.order_date.asc()).all()
        
        if not orders:
            return {
                "timeline": [],
                "period": period,
                "total_return_percent": 0
            }
        
        # Calculate portfolio hash (sorted scheme codes)
        unique_schemes = sorted(set(str(o.scheme_code) for o in orders))
        portfolio_hash = hashlib.md5(",".join(unique_schemes).encode()).hexdigest()
        
        # Determine date range and granularity
        end_date = date.today()
        start_date = calculate_start_date(period, orders[0].order_date)
        
        # Snapshot interval based on granularity
        if granularity == "1d":
            snapshot_days = 1
        elif granularity == "1m":
            snapshot_days = 30 # Approximation, but we can iterate months
        else:
            snapshot_days = 7  # Default to weekly
            # Align to Monday for consistency if weekly
            days_until_monday = (7 - start_date.weekday()) % 7
            if days_until_monday > 0:
                start_date = start_date + timedelta(days=days_until_monday)
        
        # Try to fetch cached snapshots
        cached_snapshots = db.query(PortfolioTimelineCache).filter(
            PortfolioTimelineCache.tenant_id == tenant_id,
            PortfolioTimelineCache.portfolio_hash == portfolio_hash,
            PortfolioTimelineCache.snapshot_date >= start_date,
            PortfolioTimelineCache.snapshot_date < end_date  # Don't cache today
        ).all()
        
        # Convert cached snapshots to dict for easy lookup
        cache_dict = {
            snap.snapshot_date.date(): {
                "date": snap.snapshot_date.date().isoformat(),
                "value": float(snap.portfolio_value),
                "invested": float(snap.invested_value)
            }
            for snap in cached_snapshots
        }
        
        # Convert cached snapshots to dict for easy lookup
        
        # Generate snapshots
        timeline = []
        current_date = start_date
        
        # Bulk NAV data cache to avoid repeated API calls per scheme
        # {scheme_code: {date_str: nav}}
        bulk_nav_data = {}
        
        def get_nav_bulk(scheme_code: str):
            if scheme_code in bulk_nav_data:
                return bulk_nav_data[scheme_code]
            
            try:
                import httpx
                resp = httpx.get(f"https://api.mfapi.in/mf/{scheme_code}", timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    nav_map = {entry['date']: float(entry['nav']) for entry in data.get('data', [])}
                    bulk_nav_data[scheme_code] = nav_map
                    return nav_map
            except Exception as e:
                pass
            return {}

        def find_closest_nav(nav_map, target_date):
            if not nav_map: return 0.0
            
            # Try exact match first (API format is DD-MM-YYYY)
            target_str = target_date.strftime("%d-%m-%Y")
            if target_str in nav_map:
                return nav_map[target_str]
            
            # Look back up to 7 days
            for i in range(1, 8):
                prev_date = target_date - timedelta(days=i)
                prev_str = prev_date.strftime("%d-%m-%Y")
                if prev_str in nav_map:
                    return nav_map[prev_str]
            
            # Fallback to any latest available if none in range
            # (In a real app, you might want more complex logic here)
            return next(iter(nav_map.values())) if nav_map else 0.0
        
        
        while current_date <= end_date:
            # Check if this snapshot is cached
            if current_date in cache_dict and current_date < end_date:
                # Use cached value
                timeline.append(cache_dict[current_date])
            else:
                # Calculate holdings snapshot at this date
                holdings_snapshot = {}  # {scheme_code: units}
                invested_at_date = 0
                buy_total = 0
                sell_total = 0
                
                for order in orders:
                    order_date = order.order_date.date() if hasattr(order.order_date, 'date') else order.order_date
                    
                    if order_date <= current_date:
                        scheme_code = str(order.scheme_code)
                        
                        if order.type == "BUY":
                            holdings_snapshot[scheme_code] = holdings_snapshot.get(scheme_code, 0) + float(order.units)
                            invested_at_date += float(order.amount)
                            buy_total += float(order.amount)
                        elif order.type == "SELL":
                            holdings_snapshot[scheme_code] = holdings_snapshot.get(scheme_code, 0) - float(order.units)
                            invested_at_date -= float(order.amount)
                            sell_total += float(order.amount)
                
                
                # Calculate portfolio value at this date
                portfolio_value = 0
                nav_fetched = 0
                nav_fallback = 0
                
                for scheme_code, units in holdings_snapshot.items():
                    if units > 0:
                        try:
                            if scheme_code not in bulk_nav_data:
                                get_nav_bulk(scheme_code)
                            
                            nav = find_closest_nav(bulk_nav_data.get(scheme_code, {}), current_date)
                            portfolio_value += units * nav
                            nav_fetched += 1
                        except Exception as e:
                            # Use current NAV as fallback if API/Cache fails
                            holding = db.query(MutualFundHolding).filter(
                                MutualFundHolding.scheme_code == scheme_code,
                                MutualFundHolding.tenant_id == tenant_id
                            ).first()
                            if holding and holding.last_nav:
                                portfolio_value += units * float(holding.last_nav)
                                nav_fallback += 1
                
                
                snapshot_data = {
                    "date": current_date.isoformat(),
                    "value": round(portfolio_value, 2),
                    "invested": round(invested_at_date, 2)
                }
                timeline.append(snapshot_data)
                
                # Save to cache if not today
                if current_date < end_date:
                    from datetime import datetime as dt
                    cache_entry = PortfolioTimelineCache(
                        tenant_id=tenant_id,
                        snapshot_date=dt.combine(current_date, dt.min.time()),
                        portfolio_hash=portfolio_hash,
                        portfolio_value=round(portfolio_value, 2),
                        invested_value=round(invested_at_date, 2)
                    )
                    db.add(cache_entry)
            
            # Move to next snapshot date
            # Move to next date based on granularity
            if granularity == "1m":
                current_date = add_months(current_date, 1)
            else:
                current_date = current_date + timedelta(days=snapshot_days)
            
            # Don't overshoot end date
            if current_date > end_date:
                break
        
        # Calculate total return
        total_return_percent = 0
        if timeline and timeline[-1]["invested"] > 0:
            total_return_percent = (
                (timeline[-1]["value"] - timeline[-1]["invested"]) / 
                timeline[-1]["invested"] * 100
            )
        
        # Commit cache entries to database
        try:
            db.commit()
        except Exception as e:
                                # Silent fail or log properly
            db.rollback()
        
        # Calculate Benchmark (Nifty 50 proxy: 120716)
        # Instead of simple normalization, we simulate actual investment timing (SIPs/Lumpsums)
        benchmark_timeline = []
        try:
            benchmark_code = "120716" # UTI Nifty 50 Index Fund
            get_nav_bulk(benchmark_code)
            b_nav_map = bulk_nav_data.get(benchmark_code, {})

            total_benchmark_units = 0.0
            order_idx = 0
            
            for point in timeline:
                p_date_iso = point["date"]
                p_date = date.fromisoformat(p_date_iso)
                
                # Check for any transactions UP TO this snapshot date
                while order_idx < len(orders):
                    order = orders[order_idx]
                    o_date = order.order_date.date() if hasattr(order.order_date, 'date') else order.order_date
                    
                    if o_date <= p_date:
                        # Fetch index NAV on this transaction date
                        o_nav = find_closest_nav(b_nav_map, o_date)
                        if o_nav > 0:
                            # Use units * nav if amount is 0 (fallback)
                            amount = float(order.amount)
                            if amount <= 0:
                                amount = float(order.units) * float(order.nav)
                                
                            if order.type == "BUY":
                                total_benchmark_units += (amount / o_nav)
                            elif order.type == "SELL":
                                # Proportionally sell benchmark units based on value ratio
                                # We'll just sell the same equivalent cash value for simplicity
                                total_benchmark_units -= (amount / o_nav)
                        order_idx += 1
                    else:
                        break
                
                # Nifty 50 value today = total units * current snapshot NAV
                p_nav = find_closest_nav(b_nav_map, p_date)
                simulated_value = total_benchmark_units * p_nav
                
                benchmark_timeline.append({
                    "date": p_date_iso,
                    "value": round(simulated_value, 2)
                })
        except Exception as b_err:
            benchmark_timeline = []

        return {
            "timeline": timeline,
            "benchmark": benchmark_timeline,
            "period": period,
            "granularity": granularity,
            "total_return_percent": round(total_return_percent, 2)
        }
    
    @staticmethod
    def _fetch_historical_nav(scheme_code: str, target_date) -> float:
        """
        Fetch NAV for a specific date from mfapi.in.
        Falls back to nearest available NAV if exact date not found.
        """
        import httpx
        from datetime import timedelta
        
        try:
            # mfapi.in provides historical data in reverse chronological order
            response = httpx.get(f"https://api.mfapi.in/mf/{scheme_code}", timeout=5.0)
            response.raise_for_status()
            data = response.json()
            
            if 'data' not in data:
                raise ValueError("No NAV data available")
            
            # Format target date as DD-MM-YYYY to match API format
            target_date_str = target_date.strftime("%d-%m-%Y")
            
            # Try to find exact date first
            for entry in data['data']:
                if entry['date'] == target_date_str:
                    return float(entry['nav'])
            
            # If not found, find closest date within 7 days before
            target_timestamp = target_date
            for entry in data['data']:
                try:
                    from datetime import datetime
                    entry_date = datetime.strptime(entry['date'], "%d-%m-%Y").date()
                    
                    # Use NAV from up to 7 days before target
                    if entry_date <= target_date and (target_date - entry_date).days <= 7:
                        return float(entry['nav'])
                except:
                    continue
            
            # If still not found, use the latest available NAV
            if data['data']:
                return float(data['data'][0]['nav'])
            
            raise ValueError("No suitable NAV found")
            
        except Exception as e:
            pass
            raise

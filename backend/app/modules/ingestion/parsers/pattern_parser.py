import re
import json
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from backend.app.modules.ingestion import models as ingestion_models
from backend.app.modules.ingestion.base import ParsedTransaction

class PatternParser:
    @staticmethod
    def parse(db: Session, tenant_id: str, content: str, source: str, date_hint: Optional[datetime] = None) -> Optional[ParsedTransaction]:
        patterns = db.query(ingestion_models.ParsingPattern).filter(
            ingestion_models.ParsingPattern.tenant_id == tenant_id,
            ingestion_models.ParsingPattern.pattern_type == source
        ).order_by(ingestion_models.ParsingPattern.created_at.desc()).all()
        
        clean_content = " ".join(content.split())
        
        for p in patterns:
            try:
                regex = re.compile(p.pattern_value, re.IGNORECASE | re.DOTALL)
                match = regex.search(clean_content)
                if match:
                    config = json.loads(p.mapping_config)
                    
                    # Extract fields based on groups or defaults
                    def get_val(key, default=None):
                        idx = config.get(key)
                        if idx is not None and idx < len(match.groups()) + 1:
                            return match.group(idx)
                        return default

                    amount_str = get_val("amount")
                    if not amount_str: continue # Skip if no amount found
                    
                    amount = Decimal(amount_str.replace(",", ""))
                    recipient = get_val("recipient", "Unknown (Learned)")
                    account_mask = get_val("account_mask", "0000")
                    ref_id = get_val("ref_id")
                    
                    # Date handling
                    date_val = get_val("date")
                    txn_date = None
                    if date_val:
                        # Expanded formats to match PatternGenerator variations
                        formats = [
                            "%d/%m/%y", "%d-%m-%y", "%d/%m/%Y", "%d-%m-%Y",
                            "%d %b %y", "%d %b %Y", "%d-%b-%y", "%d/%m", "%d %B"
                        ]
                        for fmt in formats:
                            try:
                                txn_date = datetime.strptime(date_val, fmt)
                                # If year is missing (e.g. %d/%m), use current year
                                if txn_date.year == 1900:
                                    txn_date = txn_date.replace(year=datetime.now().year)
                                break
                            except: continue
                    
                    if not txn_date:
                        txn_date = date_hint or (datetime.now() if not date_val else None)
                    
                    # If still no date but we have a hint from message arrival, use that
                    if not txn_date:
                        txn_date = datetime.now()

                    return ParsedTransaction(
                        amount=amount,
                        date=txn_date,
                        description=f"Learned: {recipient}",
                        type=config.get("type", "DEBIT"), 
                        category=config.get("category"),
                        account_mask=account_mask,
                        recipient=recipient,
                        ref_id=ref_id,
                        raw_message=content,
                        source=source
                    )
            except Exception as e:
                pass
                continue
                
        return None

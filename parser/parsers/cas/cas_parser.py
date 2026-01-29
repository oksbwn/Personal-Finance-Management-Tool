from typing import List, Dict, Any, Optional
import casparser
import tempfile
import os
from datetime import datetime, date
from decimal import Decimal
from parser.schemas.transaction import Transaction, TransactionType, AccountInfo, MerchantInfo

class CasParser:
    """
    Wrapper around casparser library to parse Mutual Fund CAS PDFs.
    """
    
    @staticmethod
    def parse(file_bytes: bytes, password: str) -> List[Dict[str, Any]]:
        flattened_transactions = []
        
        def safe_to_dict(obj):
            if obj is None: return None
            # Core types to preserve
            if isinstance(obj, (int, float, str, bool, Decimal, datetime, date)): return obj
            
            if isinstance(obj, list): return [safe_to_dict(i) for i in obj]
            if isinstance(obj, dict): return {k: safe_to_dict(v) for k, v in obj.items()}
            
            # Pydantic or library objects
            for method in ["model_dump", "dict", "to_dict"]:
                if hasattr(obj, method):
                    try:
                        return safe_to_dict(getattr(obj, method)())
                    except: continue
            
            if hasattr(obj, "__dict__"):
                return safe_to_dict(vars(obj))
            return obj

        def safe_get(obj, key, default=None):
            if obj is None: return default
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            f.write(file_bytes)
            temp_path = f.name
            
        try:
            data = None
            # Try parsing with various successful strategies
            for strategy in [{"output": "dict"}, {"output": "dict", "force_pdfminer": True}, {"no_validate": True}, {}]:
                try:
                    data = casparser.read_cas_pdf(temp_path, password, **strategy)
                    if data: break
                except: continue
            
            if not data:
                raise ValueError("Could not parse CAS PDF. Please verify the password.")

            # Force deep conversion to ensure we only have primitive types
            data = safe_to_dict(data)

            folios = safe_get(data, "folios", [])
            for f_item in folios:
                folio = safe_to_dict(f_item)
                f_num = safe_get(folio, "folio") or safe_get(folio, "folio_no") or "Unknown"
                schemes = safe_get(folio, "schemes", [])
                
                for s_item in schemes:
                    scheme = safe_to_dict(s_item)
                    s_name = safe_get(scheme, "scheme", "Unknown Scheme")
                    
                    transactions = safe_get(scheme, "transactions", [])
                    if not transactions: continue
                    
                    for t_item in transactions:
                        txn = safe_to_dict(t_item)
                        
                        raw_date = safe_get(txn, "date")
                        if not raw_date: continue
                        
                        t_date = None
                        try:
                            if isinstance(raw_date, (datetime, date)): 
                                t_date = raw_date
                            else:
                                # String parsing
                                date_str = str(raw_date)[:10]
                                for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y"):
                                    try:
                                        t_date = datetime.strptime(date_str, fmt)
                                        break
                                    except: continue
                        except: continue

                        if not t_date: continue

                        desc = safe_get(txn, "description", "")
                        # Skip administrative or tax rows
                        if any(x in desc for x in ["Stamp Duty", "STT", "Tax"]): continue

                        t_raw = str(safe_get(txn, "type", "")).upper()
                        amt = float(safe_get(txn, "amount", 0) or 0)
                        
                        t_type = "BUY"
                        if any(x in t_raw for x in ["REDEMPTION", "SWITCH OUT"]) or amt < 0:
                            t_type = "SELL"
                        
                        flattened_transactions.append({
                            "date": t_date,
                            "type": t_type,
                            "amount": abs(amt),
                            "units": abs(float(safe_get(txn, "units", 0) or 0)),
                            "nav": float(safe_get(txn, "nav", 0) or 0),
                            "scheme_name": s_name,
                            "folio_number": f_num,
                            "amfi": safe_get(scheme, "amfi"),
                            "isin": safe_get(scheme, "isin"),
                            "description": desc,
                            "raw_message": f"{s_name} | {desc}",
                            "external_id": str(safe_get(txn, "external_id") or safe_get(txn, "ref_id") or "")
                        })
        finally:
            if os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass
                
        return flattened_transactions

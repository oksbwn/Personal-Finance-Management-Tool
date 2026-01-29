from typing import List, Dict, Any, Optional
import casparser
import tempfile
import os
from datetime import datetime
from decimal import Decimal
from parser.schemas.transaction import Transaction, TransactionType, AccountInfo, MerchantInfo

class CasParser:
    """
    Wrapper around casparser library to parse Mutual Fund CAS PDFs.
    """
    
    @staticmethod
    def parse(file_bytes: bytes, password: str) -> List[Dict[str, Any]]:
        flattened_transactions = []
        
        # Write bytes to temp file because casparser expects a file path
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            f.write(file_bytes)
            temp_path = f.name
            
        try:
            # 1. Parse PDF
            try:
                data = casparser.read_cas_pdf(temp_path, password, output="dict")
            except Exception as e:
                # Retry with force_pdfminer if first attempt fails
                try:
                    data = casparser.read_cas_pdf(temp_path, password, output="dict", force_pdfminer=True)
                except Exception as e2:
                    raise ValueError(f"Failed to parse CAS PDF: {str(e)} | {str(e2)}")

            # 2. Extract Transactions
            folios = data.get("folios", [])
            for folio in folios:
                folio_number = folio.get("folio", "Unknown")
                schemes = folio.get("schemes", [])
                
                for scheme in schemes:
                    scheme_name = scheme.get("scheme", "Unknown Scheme")
                    amfi = scheme.get("amfi", None)
                    isin = scheme.get("isin", None)
                    
                    transactions = scheme.get("transactions", [])
                    for txn in transactions:
                        # Cleaning Data
                        date_str = txn.get("date")
                        try:
                            txn_date = datetime.strptime(date_str, "%Y-%m-%d")
                        except:
                            continue

                        desc = txn.get("description", "")
                        # Skip taxes
                        if "Stamp Duty" in desc or "STT" in desc:
                            continue
                        
                        amount = float(txn.get("amount") or 0)
                        units = float(txn.get("units") or 0)
                        nav = float(txn.get("nav") or 0)
                        
                        type_str = txn.get("type", "").upper()
                        # Normalize Type
                        txn_type = "BUY"
                        if "REDEMPTION" in type_str or "SWITCH OUT" in type_str or amount < 0:
                            txn_type = "SELL"
                            amount = abs(amount)
                        
                        # We return a raw dict here because the standard Transaction schema 
                        # is bank-focused. For MF, we might need a separate schema or 
                        # map it carefully. For now, let's map to the generic Structure 
                        # but include extra meta.
                        
                        flattened_transactions.append({
                            "date": txn_date.strftime("%Y-%m-%d"),
                            "type": txn_type,
                            "amount": amount,
                            "units": units,
                            "nav": nav,
                            "scheme_name": scheme_name,
                            "folio_number": folio_number,
                            "amfi": amfi,
                            "description": desc
                        })

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
        return flattened_transactions

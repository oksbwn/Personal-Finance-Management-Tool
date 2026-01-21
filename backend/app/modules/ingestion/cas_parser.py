import casparser
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import os
import tempfile
import imaplib
import email
from email.header import decode_header
import httpx
from sqlalchemy.orm import Session
from backend.app.modules.finance.services.mutual_funds import MutualFundService

class CASParser:
    """
    Parses Consolidated Account Statements (CAS) from CAMS/KFintech using the casparser library.
    """

    @staticmethod
    def parse_pdf(file_path: str, password: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Parses a CAS PDF using the casparser library and flattens the result into a list of transactions.
        """
        flattened_transactions = []
        try:
            # Use casparser to read the PDF
            # Output structure:
            # {
            #   "file_type": "CAMS" | "KFINTECH",
            #   "folios": [
            #     {
            #       "folio": "...",
            #       "schemes": [
            #         {
            #           "scheme": "...",
            #           "transactions": [
            #             { "date": "...", "description": "...", "amount": ..., "units": ..., "nav": ..., "balance": ..., "type": "..." }
            #           ]
            #         }
            #       ]
            #     }
            #   ]
            # }
            data = casparser.read_cas_pdf(file_path, password, output="dict")
            
            # Force generic object handling because simple "dict" output seems unreliable across versions/envs
            if not isinstance(data, dict):
                if hasattr(data, "to_dict"):
                    data = data.to_dict()
                elif hasattr(data, "dict"):
                    data = data.dict()

            # Helper to get attribute or dict item safely
            def get_val(obj, key, default=None):
                if isinstance(obj, dict):
                    return obj.get(key, default)
                return getattr(obj, key, default)

            folios = get_val(data, "folios", [])
            cas_type = get_val(data, "cas_type", "UNKNOWN")
            
            print(f"[CASParser Debug] Parse type: {cas_type}. Folios found: {len(folios)}")

            # Check if it's a Summary statement with no data
            if len(folios) == 0 and cas_type == "SUMMARY":
                 raise ValueError("The uploaded file appears to be a 'Summary Statement'. Please upload a 'Detailed Transaction Statement' (e.g., from date of inception) to import your full history.")
                 
            # Fallback: If 0 folios and NOT explicitly summary (or maybe misidentified), try force_pdfminer
            if len(folios) == 0:
                print("[CASParser] No folios found. Retrying with force_pdfminer=True...")
                try:
                    data = casparser.read_cas_pdf(file_path, password, output="dict", force_pdfminer=True)
                    if not isinstance(data, dict):
                         if hasattr(data, "to_dict"):
                            data = data.to_dict()
                         elif hasattr(data, "dict"):
                            data = data.dict()
                    
                    folios = get_val(data, "folios", [])
                    print(f"[CASParser Debug] Retry parse type: {type(data)}. Folios found: {len(folios)}")
                except Exception as e:
                    print(f"[CASParser Debug] Retry failed: {e}")

            # Debug: Print raw keys if still empty
            if len(folios) == 0:
                print(f"[CASParser] RAW DATA DUMP: {data}")
            print(f"[CASParser Debug] Found {len(folios)} folios in CAS data.")
            
            for folio in folios:
                folio_number = get_val(folio, "folio", "Unknown")
                schemes = get_val(folio, "schemes", [])
                print(f"[CASParser Debug] Folio {folio_number} has {len(schemes)} schemes.")
                
                for scheme in schemes:
                    scheme_name = get_val(scheme, "scheme", "Unknown Scheme")
                    amfi = get_val(scheme, "amfi", None)
                    isin = get_val(scheme, "isin", None)
                    
                    transactions = get_val(scheme, "transactions", [])
                    print(f"[CASParser Debug] Scheme '{scheme_name}' has {len(transactions)} transactions.")
                    
                    for txn in transactions:
                        # Convert date string to datetime object
                        # casparser returns date in 'YYYY-MM-DD' usually OR a date object
                        raw_date = get_val(txn, "date")
                        txn_date = None

                        if isinstance(raw_date, (datetime, date)):
                             txn_date = raw_date
                        elif isinstance(raw_date, str):
                            try:
                                txn_date = datetime.strptime(raw_date, "%Y-%m-%d")
                            except ValueError:
                                # Fallback or keep string? The Service expects datetime usually
                                try:
                                    txn_date = datetime.strptime(raw_date, "%d-%b-%Y")
                                except:
                                    pass

                        if not txn_date:
                            continue # Skip invalid dates

                        # SKIP non-investment transactions (Taxes, Stamp Duty)
                        description = get_val(txn, "description", "")
                        if "Stamp Duty" in description or "STT" in description or "Tax" in description:
                             continue

                        # Map casparser transaction type to our system's type if needed
                        # casparser transactions usually have type
                        t_type = get_val(txn, "type", "").upper()
                        final_type = "BUY"
                        amount = get_val(txn, "amount", 0) or 0
                        if "REDEMPTION" in t_type or "SWITCH OUT" in t_type or amount < 0:
                            final_type = "SELL"
                        
                        # Handle specific purchase types
                        if "PURCHASE" in t_type or "SWITCH IN" in t_type:
                            final_type = "BUY"
                            
                        units = get_val(txn, "units")
                        nav = get_val(txn, "nav")

                        flattened_transactions.append({
                            "date": txn_date,
                            "scheme_name": scheme_name,
                            "amfi": amfi,
                            "isin": isin,
                            "folio_number": folio_number,
                            "type": final_type,
                            "amount": abs(float(amount)),
                            "units": float(units or 0.0),
                            "nav": float(nav or 0.0),
                            "raw_line": get_val(txn, "description", ""),
                            "external_id": get_val(txn, "external_id") 
                        })
                
            print(f"[CASParser] Extracted {len(flattened_transactions)} transactions using casparser.")
                
        except Exception as e:
            print(f"[CASParser] Error parsing PDF with casparser: {e}")
            raise e
            
        return flattened_transactions

    @staticmethod
    def _extract_transactions_from_text(text: str) -> List[Dict[str, Any]]:
        # Deprecated: usage of casparser library replaces this method
        return []

    @staticmethod
    def scan_cas_emails(
        email_config: object, 
        password: str
    ) -> List[Dict[str, Any]]:
        """
        Scan emails for CAS, parse PDFs, and return a flattened list of all raw transactions.
        Does NOT ingest into DB. Mapping and ingestion happen in MutualFundService.
        """
        all_found_transactions = []
        
        try:
            mail = imaplib.IMAP4_SSL(email_config.imap_server)
            mail.login(email_config.email, email_config.password)
            mail.select(email_config.folder)
            
            search_query = '(OR (SUBJECT "Consolidated Account Statement") (FROM "camsonline"))'
            if email_config.cas_last_sync_at:
                imap_date = email_config.cas_last_sync_at.strftime("%d-%b-%Y")
                search_query = f'({search_query} SINCE {imap_date})'
                
            status, messages = mail.search(None, search_query)
            if status != "OK":
                return []
                
            email_ids = messages[0].split()
            print(f"[CASParser] Found {len(email_ids)} CAS emails to scan.")

            for e_id in email_ids:
                _, msg_data = mail.fetch(e_id, "(BODY.PEEK[])")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                for part in msg.walk():
                    if part.get_content_maintype() == 'multipart' or part.get('Content-Disposition') is None:
                        continue
                        
                    filename = part.get_filename()
                    if filename and filename.lower().endswith('.pdf'):
                        print(f"[CASParser] Scanning PDF from email: {filename}")
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
                            f.write(part.get_payload(decode=True))
                            temp_path = f.name
                            
                        try:
                            transactions = CASParser.parse_pdf(temp_path, password)
                            all_found_transactions.extend(transactions)
                        except Exception as parse_err:
                            print(f"[CASParser] Parse error for {filename}: {parse_err}")
                        finally:
                            if os.path.exists(temp_path):
                                os.remove(temp_path)

            mail.close()
            mail.logout()
            
        except Exception as e:
            print(f"[CASParser] Connection error: {e}")
            raise e
            
        return all_found_transactions

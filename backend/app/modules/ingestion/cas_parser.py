import pdfplumber
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
import os
import tempfile
import imaplib
import email
from email.header import decode_header
from sqlalchemy.orm import Session
from backend.app.modules.finance.services.mutual_funds import MutualFundService

class CASParser:
    """
    Parses Consolidated Account Statements (CAS) from CAMS/KFintech.
    Supports PDF password decryption.
    """

    @staticmethod
    def parse_pdf(file_path: str, password: Optional[str] = None) -> List[Dict[str, Any]]:
        transactions = []
        try:
            with pdfplumber.open(file_path, password=password) as pdf:
                full_text = ""
                for page in pdf.pages:
                    full_text += page.extract_text() + "\n"
                
                # Basic parsing logic (This is highly simplified and needs robust regex for real CAS)
                # We look for lines that might look like transactions
                # Date       Scheme                     Amount      Units      NAV      Type
                # 01-Jan-24  HDFC Top 100 Fund ...      5000.00     10.23      245.20   Purchase
                
                # Regex to find Scheme Name (heuristic: line starts with specific words or formatting)
                # Then regex to find transaction rows below it
                
                # Placeholder for actual complex parsing logic
                print(f"[CASParser] Extracted {len(full_text)} chars.")
                transactions = CASParser._extract_transactions_from_text(full_text)
                
        except Exception as e:
            print(f"[CASParser] Error parsing PDF: {e}")
            raise e
            
        return transactions

    @staticmethod
    def _extract_transactions_from_text(text: str) -> List[Dict[str, Any]]:
        extracted = []
        lines = text.split('\n')
        current_scheme = None
        current_folio = None
        
        # Regex patterns (Examples - need refinement based on actual CAS format)
        scheme_pattern = re.compile(r"Folio No:\s*(\S+).+Scheme:\s*(.+)") 
        # CAMS CAS often has "Folio No: 123456 / ... Scheme: HDFC ..."
        
        # Date pattern: DD-Mon-YYYY or DD/MM/YYYY
        date_pattern = re.compile(r"(\d{2}-[A-Za-z]{3}-\d{4})")
        
        for line in lines:
            # 1. Detect Scheme/Folio
            # This is tricky in text dump. Often Folio is on one line, Scheme on another.
            # Simplified assumption for prototype:
            if "Folio No" in line:
                # Try to grab folio
                parts = line.split("Folio No")
                if len(parts) > 1:
                    # simplistic extraction
                    current_folio = parts[1].split()[0].replace(":", "").strip()
            
            if "Scheme" in line or ("Fund" in line and "Plan" in line):
                 # simplistic scheme detection
                 current_scheme = line.strip()

            # 2. Detect Transaction Line
            # Look for Date + Amount + Units
            date_match = date_pattern.search(line)
            if date_match:
                # It's a potential transaction line
                try:
                    # Parse parts
                    # 02-Jan-2023   SIP Purchase    1,000.00    12.234    145.23
                    parts = line.split()
                    date_str = date_match.group(1)
                    date = datetime.strptime(date_str, "%d-%b-%Y")
                    
                    # Heuristic: Find amount (look for numbers with decimals)
                    # This is fragile without column extraction, but okay for V1 prototype
                    numbers = [float(p.replace(",", "")) for p in parts if re.match(r"^-?\d{1,3}(,\d{3})*(\.\d+)?$", p)]
                    
                    if len(numbers) >= 3:
                        # Assume: Amount, Units, NAV (order varies)
                        # Usually: Amount, Price(NAV), Units -> CAMS
                        # Let's assume standard CAMS ordering or just take distinct values
                        
                        # Logic: Amount is usually the nice round number or largest? 
                        # NAV is roughly 10-1000. Units depends.
                        # Validate against Amount ~= Units * NAV
                        
                        amount = numbers[0]
                        nav = numbers[1]
                        units = numbers[2]
                        
                        # Verify math
                        if abs(amount - (units * nav)) > 1.0:
                             # Try other permutations
                             if abs(numbers[0] - (numbers[1] * numbers[2])) < 1.0:
                                 amount = numbers[0]
                                 units = numbers[1]
                                 nav = numbers[2]
                        
                        # Determine Type
                        trans_type = "BUY"
                        if "Redemption" in line or "Switch Out" in line or amount < 0:
                            trans_type = "SELL"
                            amount = abs(amount)
                        
                        if current_scheme:
                            extracted.append({
                                "date": date,
                                "scheme_name": current_scheme, # We need to map this to Scheme Code later!
                                "folio_number": current_folio,
                                "type": trans_type,
                                "amount": amount,
                                "units": units,
                                "nav": nav,
                                "raw_line": line
                            })
                except:
                    pass
                    
        return extracted

    @staticmethod
    def find_and_process_cas_emails(
        db: Session, 
        tenant_id: str,
        email_config: object, # SQLAlchemy object
        password: str
    ):
        """
        Connects to email, searches for CAS emails, downloads attachment, parses, and ingests.
        """
        stats = {"found": 0, "processed": 0, "errors": []}
        
        try:
            # 1. Connect IMAP
            mail = imaplib.IMAP4_SSL(email_config.imap_server)
            mail.login(email_config.email, email_config.password)
            mail.select(email_config.folder)
            
            # 2. Search for CAS
            # Criteria: Subject "Consolidated Account Statement" OR From "camsonline"
            search_query = '(OR (SUBJECT "Consolidated Account Statement") (FROM "camsonline"))'
            status, messages = mail.search(None, search_query)
            
            if status != "OK":
                return stats
                
            email_ids = messages[0].split()
            stats["found"] = len(email_ids)
            print(f"[CASParser] Found {len(email_ids)} CAS emails.")

            for e_id in email_ids:
                # Fetch latest first? email_ids are usually chronological.
                # Let's just process the last one for now? Or all? 
                # For "Sync", maybe process all.
                
                _, msg_data = mail.fetch(e_id, "(RFC822)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                # Check attachments
                for part in msg.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get('Content-Disposition') is None:
                        continue
                        
                    filename = part.get_filename()
                    if filename and filename.lower().endswith('.pdf'):
                        # Found PDF
                        print(f"[CASParser] Found PDF: {filename}")
                        
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
                            f.write(part.get_payload(decode=True))
                            temp_path = f.name
                            
                        try:
                            # Parse
                            transactions = CASParser.parse_pdf(temp_path, password)
                            print(f"[CASParser] Extracted {len(transactions)} transactions.")
                            
                            # Ingest
                            for txn in transactions:
                                # 1. Resolve Scheme Code from Name using simple search
                                results = MutualFundService.search_funds(txn['scheme_name'])
                                if results:
                                    best_match = results[0] # Naive
                                    txn['scheme_code'] = best_match['schemeCode']
                                    
                                    MutualFundService.add_transaction(db, tenant_id, txn)
                                    stats["processed"] += 1
                                else:
                                    print(f"Could not map scheme: {txn['scheme_name']}")
                                    
                        except Exception as parse_err:
                            stats["errors"].append(str(parse_err))
                            print(f"[CASParser] Parse error: {parse_err}")
                        finally:
                            os.remove(temp_path)

            mail.close()
            mail.logout()
            
        except Exception as e:
            stats["errors"].append(str(e))
            print(f"[CASParser] connection error: {e}")
            
        return stats

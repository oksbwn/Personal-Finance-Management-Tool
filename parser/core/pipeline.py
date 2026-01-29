from sqlalchemy.orm import Session
from typing import Optional, Any
from parser.core.classifier import FinancialClassifier
from parser.parsers.registry import ParserRegistry
from parser.db.models import RequestLog
import hashlib
import json
from datetime import datetime, timedelta
from rapidfuzz import fuzz
from decimal import Decimal
from parser.schemas.transaction import Transaction, IngestionResult, ParsedItem, AccountInfo, MerchantInfo, TransactionType
from parser.parsers.patterns.regex_engine import PatternParser
from parser.parsers.ai.gemini_parser import GeminiParser
from parser.core.normalizer import MerchantNormalizer
from parser.core.validator import TransactionValidator
from parser.core.guesser import CategoryGuesser

class IngestionPipeline:

    def __init__(self, db: Session):
        self.db = db

    def _convert_to_schema_txn(self, pt: Any) -> Transaction:
        """Helper to convert backend-style ParsedTransaction or dict to microservice Transaction"""
        
        
        # If it's already a Transaction object (from AI or Pattern parser)
        if isinstance(pt, Transaction):
            return pt
            
        # If it's a dict or dict-like (from UniversalParser or legacy CAS logs)
        if isinstance(pt, dict) or hasattr(pt, 'amount') or hasattr(pt, 'date'):
            def safe_pt_get(key, default=None):
                if isinstance(pt, dict):
                    return pt.get(key, default)
                return getattr(pt, key, default)

            # Handle CAS/MF specific mappings
            raw_type = str(safe_pt_get("type", "DEBIT")).upper()
            txn_type = TransactionType.DEBIT
            if raw_type in ["CREDIT", "SELL", "REDEMPTION"]:
                txn_type = TransactionType.CREDIT
            elif raw_type in ["DEBIT", "BUY", "INVESTMENT"]:
                txn_type = TransactionType.DEBIT

            # Merchant mapping
            m_raw = safe_pt_get("description") or safe_pt_get("scheme_name") or "Unknown"
            m_clean = safe_pt_get("recipient") or safe_pt_get("scheme_name") or m_raw

            # Handle date parsing
            pt_date = pt.get("date") if isinstance(pt, dict) else getattr(pt, "date", None)
            if isinstance(pt_date, str):
                final_date = datetime.fromisoformat(pt_date)
            else:
                final_date = pt_date

            return Transaction(
                amount=Decimal(str(safe_pt_get("amount", 0))),
                type=txn_type,
                date=final_date,
                account=AccountInfo(mask=safe_pt_get("account_mask") or safe_pt_get("folio_number") or safe_pt_get("external_id")),
                merchant=MerchantInfo(raw=m_raw, cleaned=m_clean),
                description=safe_pt_get("description") or safe_pt_get("scheme_name"),
                ref_id=safe_pt_get("external_id") or safe_pt_get("ref_id") or safe_pt_get("folio_number"),
                balance=Decimal(str(safe_pt_get("balance"))) if safe_pt_get("balance") else None,
                category=safe_pt_get("category") or ("Mutual Fund" if safe_pt_get("scheme_name") else None),
                recipient=safe_pt_get("recipient") or safe_pt_get("scheme_name"),
                raw_message=safe_pt_get("raw_message") or (
                    getattr(safe_pt_get("original_row"), "description", "Imported") if safe_pt_get("original_row") and not isinstance(safe_pt_get("original_row"), dict) 
                    else (safe_pt_get("original_row") or {}).get("description", "Imported") if isinstance(safe_pt_get("original_row"), dict) 
                    else "Imported"
                )
            )
            
        # If it's a backend ParsedTransaction
        return Transaction(
            amount=pt.amount,
            type=TransactionType.DEBIT if pt.type == "DEBIT" else TransactionType.CREDIT,
            date=pt.date,
            account=AccountInfo(mask=pt.account_mask),
            merchant=MerchantInfo(raw=pt.recipient or pt.description, cleaned=pt.recipient or pt.description),
            description=pt.description,
            ref_id=pt.ref_id,
            balance=pt.balance,
            category=pt.category,
            recipient=pt.recipient,
            raw_message=pt.raw_message
        )

    def run(self, content: str, source: str, sender: Optional[str] = None, subject: Optional[str] = None) -> IngestionResult:
        # 1. Idempotency Check
        input_hash = hashlib.sha256(f"{source}:{content}".encode()).hexdigest()
        
        # Check last 5 mins
        cutoff = datetime.utcnow() - timedelta(minutes=5)
        existing = self.db.query(RequestLog).filter(
            RequestLog.input_hash == input_hash,
            RequestLog.created_at >= cutoff
        ).first()

        if existing:
            return IngestionResult(status="duplicate_submission", results=[], logs=["Duplicate submission detected"])

        # Create Log Entry
        log = RequestLog(input_hash=input_hash, source=source, input_payload={"content": content, "sender": sender, "subject": subject}, status="processing")
        self.db.add(log)
        self.db.commit()

        logs = []

        # 2. Classification
        if not FinancialClassifier.is_financial(content, source):
            log.status = "ignored"
            self.db.commit()
            return IngestionResult(status="ignored", results=[], logs=["Classified as non-financial"])

        # 3. Extraction Chain
        parsed_txn = None
        parser_used = "Unknown"
        
        # A. Static Parsers
        parsers = ParserRegistry.get_sms_parsers() if source == "SMS" else ParserRegistry.get_email_parsers()
        for p in parsers:
            can_handle = False
            try:
                if source == "SMS":
                    can_handle = p.can_handle(sender or "", content)
                else:
                    can_handle = p.can_handle(subject or "", content)
            except Exception as e:
                logs.append(f"can_handle failed for {type(p).__name__}: {str(e)}")
                
            if can_handle:
                try:
                    pt = p.parse(content)
                    if pt:
                        parsed_txn = self._convert_to_schema_txn(pt)
                        parser_used = getattr(p, 'name', type(p).__name__)
                        logs.append(f"Successfully parsed by {parser_used}")
                        break
                except Exception as e:
                    logs.append(f"Parser {type(p).__name__} failed: {str(e)}")

        # B. User Patterns
        if not parsed_txn:
             try:
                 # Load rules for this source
                 p_parser = PatternParser(self.db, source)
                 pt = p_parser.parse(content)
                 if pt:
                     parsed_txn = self._convert_to_schema_txn(pt)
                     parser_used = "User Patterns"
                     logs.append("Parsed via Patterns")
             except Exception as e:
                 logs.append(f"Pattern Parser failed: {str(e)}")

        # C. AI Fallback
        if not parsed_txn:
             try:
                 ai_parser = GeminiParser(self.db)
                 pt = ai_parser.parse(content, source)
                 if pt:
                     parsed_txn = self._convert_to_schema_txn(pt)
                     parser_used = "Gemini AI"
                     logs.append("Extracted via AI")
             except Exception as e:
                 logs.append(f"AI Parser failed: {str(e)}")


        # 4. Normalization & Validation
        if parsed_txn:
             
             
             # Normalize Merchant
             if parsed_txn.merchant:
                 # Use the recipient (if extracted) as the seed for normalization/aliasing
                 # Otherwise fallback to raw description
                 name_seed = parsed_txn.recipient or parsed_txn.merchant.raw
                 parsed_txn.merchant.cleaned = MerchantNormalizer.normalize(name_seed)
                 
                 # Update description if it was raw/missing
                 if not parsed_txn.description or parsed_txn.description == parsed_txn.merchant.raw:
                     parsed_txn.description = parsed_txn.merchant.cleaned
             
             # Enrich Time
             TransactionValidator.enrich_time(parsed_txn)
             
             # Validate
             warnings = TransactionValidator.validate(parsed_txn, content)
             if warnings:
                 logs.extend(warnings)

             # 5. Category Hint
             if not parsed_txn.category:
                parsed_txn.category = CategoryGuesser.guess(parsed_txn.merchant.cleaned, parsed_txn.description)

             # 6. Cross-Source Deduplication (New Robust Feature)
             # Check if this EXACT transaction details appeared from another source recently
             # We check logs in the last 15 minutes for similar records
             duplicate_window = datetime.utcnow() - timedelta(minutes=15)
             
             # Search previously successful extractions
             # Note: output_payload is stored as JSON in DuckDB
             # Using a slightly fuzzy match: same amount, mask, and merchant
             # Due to DuckDB JSON limitations, we fetch and filter in Python for robustness
             recent_successes = self.db.query(RequestLog).filter(
                 RequestLog.status == "success",
                 RequestLog.created_at >= duplicate_window,
                 RequestLog.input_hash != input_hash # Not ourselves
             ).all()

             is_cross_duplicate = False
             def get_digits(s): return "".join(filter(str.isdigit, str(s or "")))[-4:]
             
             for rs in recent_successes:
                 try:
                     payload = rs.output_payload or {}
                     
                     # Extract list of transactions from payload
                     prev_txns = []
                     if "results" in payload:
                         for item in payload["results"]:
                             if item.get("transaction"):
                                 prev_txns.append(item["transaction"])
                     elif "transaction" in payload:
                         prev_txns.append(payload["transaction"])
                     
                     for prev_data in prev_txns:
                         # Comparison criteria
                         same_amt = Decimal(str(prev_data["amount"])) == parsed_txn.amount
                         
                         # Check Reference ID if both have it
                         prev_ref = str(prev_data.get("ref_id") or "").strip().lstrip('0')
                         curr_ref = str(parsed_txn.ref_id or "").strip().lstrip('0')
                         same_ref = prev_ref == curr_ref if (prev_ref and curr_ref) else False
                         
                         if same_ref: # High confidence match
                              is_cross_duplicate = True
                              logs.append(f"Matching Ref ID detected from {rs.id}")
                              break

                         # Robust mask check: compare last 4 digits
                         prev_mask = get_digits(prev_data.get("account", {}).get("mask"))
                         curr_mask = get_digits(parsed_txn.account.mask if parsed_txn.account else "")
                         same_mask = prev_mask == curr_mask if (prev_mask and curr_mask) else False
                         
                         # Fuzzy merchant match
                         m_prev = (prev_data.get("merchant", {}).get("cleaned") or prev_data.get("description") or "")
                         m_curr = parsed_txn.merchant.cleaned or parsed_txn.description or ""
                         same_merchant = fuzz.partial_ratio(m_prev, m_curr) > 90
                         
                         # Same Type (Debit vs Credit)
                         same_type = prev_data.get("type") == parsed_txn.type
                         
                         if same_amt and same_mask and same_merchant and same_type:
                             is_cross_duplicate = True
                             logs.append(f"Cross-source duplicate detected from {rs.id}")
                             break
                     
                     if is_cross_duplicate:
                         break
                 except: continue

             if is_cross_duplicate:
                 log.status = "success"
                 item = ParsedItem(
                    status="cross_source_duplicate",
                    transaction=parsed_txn,
                    metadata={"confidence": 1.0, "parser_used": "Deduplicator", "source_original": source}
                 )
                 log.output_payload = item.model_dump(mode='json')
                 self.db.commit()
                 return IngestionResult(status="success", results=[item], logs=logs)

             item = ParsedItem(
                status="extracted",
                transaction=parsed_txn,
                metadata={"confidence": 0.5 if parser_used == "User Patterns" else 1.0, 
                          "parser_used": parser_used, 
                          "source_original": source}
            )
            
             # Update Log
             log.status = "success"
             log.output_payload = item.model_dump(mode='json')
             self.db.commit()
            
             return IngestionResult(status="success", results=[item], logs=logs)

        # Failed
        log.status = "failed"
        self.db.commit()
        return IngestionResult(status="failed", results=[], logs=logs + ["No parser matched"])

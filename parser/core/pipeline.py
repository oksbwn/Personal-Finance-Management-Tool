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
            
        # If it's a dict (from UniversalParser)
        if isinstance(pt, dict):
            return Transaction(
                amount=Decimal(str(pt.get("amount", 0))),
                type=TransactionType.DEBIT if pt.get("type") == "DEBIT" else TransactionType.CREDIT,
                date=datetime.fromisoformat(pt["date"]) if isinstance(pt["date"], str) else pt["date"],
                account=AccountInfo(mask=pt.get("account_mask") or pt.get("external_id")),
                merchant=MerchantInfo(raw=pt.get("description"), cleaned=pt.get("recipient") or pt.get("description")),
                description=pt.get("description"),
                ref_id=pt.get("external_id") or pt.get("ref_id"),
                balance=Decimal(str(pt["balance"])) if pt.get("balance") else None,
                category=pt.get("category"),
                raw_message=pt.get("original_row", {}).get("description", "Imported")
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
                 parsed_txn.merchant.cleaned = MerchantNormalizer.normalize(parsed_txn.merchant.raw)
                 # Update description if it was raw
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
                     prev_data = rs.output_payload.get("transaction")
                     if not prev_data: continue
                     
                     # Comparison criteria
                     same_amt = Decimal(str(prev_data["amount"])) == parsed_txn.amount
                     
                     # Robust mask check: compare last 4 digits
                     prev_mask = get_digits(prev_data["account"]["mask"])
                     curr_mask = get_digits(parsed_txn.account.mask if parsed_txn.account else "")
                     same_mask = prev_mask == curr_mask if (prev_mask and curr_mask) else False
                     
                     # Fuzzy merchant match for deduplication
                     same_merchant = fuzz.partial_ratio(prev_data["merchant"]["cleaned"], parsed_txn.merchant.cleaned) > 90
                     
                     if same_amt and same_mask and same_merchant:
                         is_cross_duplicate = True
                         logs.append(f"Cross-source duplicate detected from {rs.id}")
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

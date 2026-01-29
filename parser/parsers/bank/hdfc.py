import re
from typing import Optional
from datetime import datetime
from decimal import Decimal
from parser.parsers.base_compat import BaseSmsParser, BaseEmailParser, ParsedTransaction
from parser.parsers.utils.recipient_parser import RecipientParser

class HdfcSmsParser(BaseSmsParser):
    """
    Parser for HDFC Bank SMS Alerts.
    """
    DEBIT_PATTERN = re.compile(
        r"(?i)(?:Rs\.?|INR)\s*([\d,]+\.?\d*)\s*debited\s*from\s*a/c\s*([xX]*\d+)\s*on\s*(\d{2}-\d{2}-\d{2})\s*to\s*(.*?)\.\s*(?:Ref[:\.\s]+(\w+))?",
        re.IGNORECASE
    )
    
    SPENT_PATTERN = re.compile(
        r"(?i)Spent\s*(?:Rs\.?|INR)\s*([\d,]+\.?\d*)\s*on\s*.*?card\s*([xX]*\d+)\s*at\s*(.*?)\s*on\s*(\d{2}-\d{2}-\d{2})(?:.*?Ref:?\s*(\w+))?",
        re.IGNORECASE
    )

    # Example: "Sent Rs.75.00 From HDFC Bank A/C *5244 To Shree Krishna Sweets On 06/01/26 Ref 116777306188"
    SENT_PATTERN = re.compile(
        r"(?i)Sent\s*(?:Rs\.?|INR)\s*([\d,]+\.?\d*)\s*From\s*HDFC\s*Bank\s*A/C\s*(?:.*?|x*|\*|X*)(\d+)\s*To\s*(.*?)\s*On\s*(\d{2}/\d{2}/\d{2,4})(?:.*?Ref[:\.\s]+(\w+))?",
        re.IGNORECASE
    )

    # Example: "Rs.500.00 credited to HDFC Bank A/c XX5244 on 29-01-26 from VPA tiki08676-2@okaxis (UPI 639501711301)"
    CREDIT_PATTERN = re.compile(
        r"(?i)(?:Rs\.?|INR)\s*([\d,]+\.?\d*)\s*credited\s*to\s*HDFC\s*Bank\s*A/c\s*(?:.*?|x*|\*|X*)(\d+)\s*on\s*(\d{2}-\d{2}-\d{2,4})\s*from\s*(.*?)(?:\s*\((?:UPI|Ref)[:\.\s]*(\w+)\))?",
        re.IGNORECASE
    )

    BAL_PATTERN = re.compile(r"(?i)(?:Avbl\s*Bal|Bal|Balance)[:\.\s-]+(?:Rs\.?|INR)\s*([\d,]+\.?\d*)", re.IGNORECASE)
    LIMIT_PATTERN = re.compile(r"(?i)(?:Credit\s*Limit|Limit)[:\.\s-]+(?:Rs\.?|INR)\s*([\d,]+\.?\d*)", re.IGNORECASE)

    def can_handle(self, sender: str, message: str) -> bool:
        return "hdfc" in sender.lower() or "hdfc" in message.lower()

    def parse(self, content: str, date_hint: Optional[datetime] = None) -> Optional[ParsedTransaction]:
        clean_content = " ".join(content.split())
        
        # 1. Try Debit
        match = self.DEBIT_PATTERN.search(clean_content)
        if match:
            amount = Decimal(match.group(1).replace(",", ""))
            account_mask = match.group(2)
            date_str = match.group(3)
            recipient = match.group(4).strip()
            ref_id = match.group(5)
            return self._create_txn(amount, recipient, account_mask, date_str, "DEBIT", content, ref_id, date_hint)

        # 2. Try Spent
        match = self.SPENT_PATTERN.search(clean_content)
        if match:
            amount = Decimal(match.group(1).replace(",", ""))
            account_mask = match.group(2)
            recipient = match.group(3).strip()
            date_str = match.group(4)
            ref_id = match.group(5)
            return self._create_txn(amount, recipient, account_mask, date_str, "DEBIT", content, ref_id, date_hint)

        # 3. Try Sent
        match = self.SENT_PATTERN.search(clean_content)
        if match:
            amount = Decimal(match.group(1).replace(",", ""))
            account_mask = match.group(2)
            recipient = match.group(3).strip()
            date_str = match.group(4)
            ref_id = match.group(5)
            return self._create_txn(amount, recipient, account_mask, date_str, "DEBIT", content, ref_id, date_hint)

        # 4. Try Credit
        match = self.CREDIT_PATTERN.search(clean_content)
        if match:
            amount = Decimal(match.group(1).replace(",", ""))
            account_mask = match.group(2)
            date_str = match.group(3)
            sender_info = match.group(4).strip()
            ref_id = match.group(5)
            return self._create_txn(amount, sender_info, account_mask, date_str, "CREDIT", content, ref_id, date_hint)

        return None

    def _create_txn(self, amount, recipient, account_mask, date_str, type_str, raw, ref_id, date_hint=None):
        try:
            formats = ["%d-%m-%y", "%d-%m-%Y", "%d/%m/%y", "%d/%m/%Y"]
            txn_date = None
            for fmt in formats:
                try:
                    txn_date = datetime.strptime(date_str, fmt)
                    break
                except: continue
            if not txn_date: txn_date = date_hint or datetime.now()
        except:
            txn_date = datetime.now()
            
        clean_recipient = RecipientParser.extract(recipient)
        return ParsedTransaction(
            amount=amount,
            date=txn_date,
            description=f"HDFC: {clean_recipient or recipient}",
            type=type_str,
            account_mask=account_mask,
            recipient=clean_recipient,
            ref_id=ref_id,
            balance=self._find_balance(raw),
            credit_limit=self._find_limit(raw),
            raw_message=raw,
            source="SMS"
        )

    def _find_balance(self, content: str) -> Optional[Decimal]:
        match = self.BAL_PATTERN.search(content)
        if match:
            return Decimal(match.group(1).replace(",", ""))
        return None

    def _find_limit(self, content: str) -> Optional[Decimal]:
        match = self.LIMIT_PATTERN.search(content)
        if match:
            return Decimal(match.group(1).replace(",", ""))
        return None

class HdfcEmailParser(BaseEmailParser):
    """
    Parser for HDFC Bank Email Alerts.
    """
    DEBIT_CARD_PATTERN = re.compile(
        r"(?i)made\s*a\s*transaction\s*of\s*(?:Rs\.?|INR)\s*([\d,]+\.?\d*)\s*on\s*your\s*HDFC\s*Bank\s*.*?(?:Card)\s*(?:.*?|x*|X*)(\d+)\s*at\s*(.*?)\s*on\s*(\d{2}-\d{2}-\d{2,4})(?:.*?Ref[:\.\s]+(\w+))?",
        re.IGNORECASE
    )

    ACCOUNT_DEBIT_PATTERN = re.compile(
        r"(?i)A/c\s*(?:.*?|x*|X*)(\d+)\s*has\s*been\s*debited\s*for\s*(?:Rs\.?|INR)\s*([\d,]+\.?\d*)\s*on\s*(\d{2}-\d{2}-\d{2,4})\s*towards\s*(.*?)(?:\.\s*Ref[:\s]+(\w+))?",
        re.IGNORECASE
    )

    # Example: "Rs.40000.00 has been debited from account 5244 to VPA groww.iccl1.brk@validhdfc MUTUAL FUNDS ICCL on 13-01-26. Ref: 116929657356"
    # Example 2: "Dear Customer, Rs.35.00 has been debited from account 5244 to VPA ... on 28-01-26. Your UPI transaction reference number is 1178..."
    UPI_DEBIT_PATTERN = re.compile(
        r"(?i)(?:Rs\.?|INR)\s*([\d,]+\.?\d*)\s*has\s*been\s*debited\s*from\s*account\s*(\d+)\s*to\s*(.*?)\s*on\s*(\d{2}-\d{2}-\d{2,4})(?:.*?\b(?:Ref|Reference)\s*(?:No|ID|Number)?[\s:\.-]+([a-zA-Z0-9]+))?",
        re.IGNORECASE
    )

    # Example: "❗ You have done a UPI txn. Rs.10.00 debited from A/c XX1234 to MERCHANT on 13-01-26. Ref: 123"
    GENERIC_UPI_PATTERN = re.compile(
        r"(?i)UPI\s*txn.*?([\d,]+\.?\d*)\s*debited\s*from\s*A/c\s*(?:.*?|x*|X*)(\d+)\s*to\s*(.*?)\s*on\s*(\d{2}-\d{2}-\d{2,4})(?:.*?\b(?:Ref|Reference)\s*(?:No|ID|Number)?[\s:\.-]+([a-zA-Z0-9]+))?",
        re.IGNORECASE
    )

    # More flexible pattern for Reference/UTR
    # Updated to allow "is" as separator e.g. "Reference number is 123"
    REF_PATTERN = re.compile(
        r"(?i)\b(?:Ref|UTR|TXN#|Ref\s*No|Reference\s*ID|reference\s*number|utr\s*no|Ref\s*ID)(?:[\s:\.-]|\bis\b)+([a-zA-Z0-9]{3,})", 
        re.IGNORECASE
    )

    BAL_PATTERN = re.compile(r"(?i)\b(?:Avbl\s*Bal|Bal|Balance)[:\.\s-]+(?:Rs\.?|INR)\s*([\d,]+\.?\d*)", re.IGNORECASE)
    LIMIT_PATTERN = re.compile(r"(?i)\b(?:Credit\s*Limit|Limit)[:\.\s-]+(?:Rs\.?|INR)\s*([\d,]+\.?\d*)", re.IGNORECASE)

    def can_handle(self, subject: str, body: str) -> bool:
        combined = (subject + " " + body).lower()
        # If the subject is the specific HDFC UPI alert subject, handle it
        if "you have done a upi txn" in combined:
            return True
        if "hdfc" not in combined:
            return False
        keywords = ["transaction", "debited", "spent", "txn", "upi", "vpa", "rs"]
        return any(k in combined for k in keywords)

    def parse(self, content: str, date_hint: Optional[datetime] = None) -> Optional[ParsedTransaction]:
        clean_content = " ".join(content.split())
        
        def get_ref(match, group_idx):
            if group_idx < len(match.groups()) + 1 and match.group(group_idx): 
                return match.group(group_idx)
            
            # Fallback 1: Search for improved REF_PATTERN
            ref_match = self.REF_PATTERN.search(clean_content)
            if ref_match: return ref_match.group(1).strip()
            
            # Fallback 2: Look for 12-digit UPI Ref specifically if "reference" or "Ref" is present
            if any(k in clean_content.lower() for k in ["reference", "ref no", "utr"]):
                digits_match = re.search(r"(\d{12})", clean_content)
                if digits_match: return digits_match.group(1)
                
            return None

        # 1. Card
        match = self.DEBIT_CARD_PATTERN.search(clean_content)
        if match:
            return self._create_txn(Decimal(match.group(1).replace(",", "")), match.group(3), match.group(2), match.group(4), "DEBIT", content, get_ref(match, 5), date_hint)

        # 2. Account
        match = self.ACCOUNT_DEBIT_PATTERN.search(clean_content)
        if match:
            return self._create_txn(Decimal(match.group(2).replace(",", "")), match.group(4), match.group(1), match.group(3), "DEBIT", content, get_ref(match, 5), date_hint)

        # 3. UPI
        match = self.UPI_DEBIT_PATTERN.search(clean_content)
        if match:
            return self._create_txn(Decimal(match.group(1).replace(",", "")), match.group(3), match.group(2), match.group(4), "DEBIT", content, get_ref(match, 5), date_hint)

        # 4. Generic UPI
        match = self.GENERIC_UPI_PATTERN.search(clean_content)
        if match:
            return self._create_txn(Decimal(match.group(1).replace(",", "")), match.group(3), match.group(2), match.group(4), "DEBIT", content, get_ref(match, 5), date_hint)

        return None

    def _create_txn(self, amount, recipient, account_mask, date_str, type_str, raw, ref_id, date_hint=None):
        try:
            formats = ["%d-%m-%y", "%d-%m-%Y", "%d/%m/%y", "%d/%m/%Y"]
            txn_date = None
            for fmt in formats:
                try:
                    txn_date = datetime.strptime(date_str, fmt)
                    break
                except: continue
            if not txn_date: txn_date = date_hint or datetime.now()
        except:
            txn_date = datetime.now()
            
        clean_recipient = RecipientParser.extract(recipient)
        return ParsedTransaction(
            amount=amount,
            date=txn_date,
            description=f"HDFC: {clean_recipient or recipient}",
            type=type_str,
            account_mask=account_mask,
            recipient=clean_recipient,
            ref_id=ref_id,
            balance=self._find_balance(raw),
            credit_limit=self._find_limit(raw),
            raw_message=raw,
            source="EMAIL"
        )

    def _find_balance(self, content: str) -> Optional[Decimal]:
        match = self.BAL_PATTERN.search(content)
        if match:
            return Decimal(match.group(1).replace(",", ""))
        return None

    def _find_limit(self, content: str) -> Optional[Decimal]:
        match = self.LIMIT_PATTERN.search(content)
        if match:
            return Decimal(match.group(1).replace(",", ""))
        return None

import re
from typing import Optional
from datetime import datetime
from decimal import Decimal
from backend.app.modules.ingestion.base import BaseSmsParser, BaseEmailParser, ParsedTransaction
from backend.app.modules.ingestion.parsers.recipient_parser import RecipientParser

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

    def can_handle(self, sender: str, message: str) -> bool:
        return "hdfc" in sender.lower() or "hdfc" in message.lower()

    def parse(self, content: str) -> Optional[ParsedTransaction]:
        clean_content = " ".join(content.split())
        
        # 1. Try Debit
        match = self.DEBIT_PATTERN.search(clean_content)
        if match:
            amount = Decimal(match.group(1).replace(",", ""))
            account_mask = match.group(2)
            date_str = match.group(3)
            recipient = match.group(4).strip()
            ref_id = match.group(5)
            return self._create_txn(amount, recipient, account_mask, date_str, "DEBIT", content, ref_id)

        # 2. Try Spent
        match = self.SPENT_PATTERN.search(clean_content)
        if match:
            amount = Decimal(match.group(1).replace(",", ""))
            account_mask = match.group(2)
            recipient = match.group(3).strip()
            date_str = match.group(4)
            ref_id = match.group(5)
            return self._create_txn(amount, recipient, account_mask, date_str, "DEBIT", content, ref_id)

        # 3. Try Sent
        match = self.SENT_PATTERN.search(clean_content)
        if match:
            amount = Decimal(match.group(1).replace(",", ""))
            account_mask = match.group(2)
            recipient = match.group(3).strip()
            date_str = match.group(4)
            ref_id = match.group(5)
            return self._create_txn(amount, recipient, account_mask, date_str, "DEBIT", content, ref_id)

        return None

    def _create_txn(self, amount, recipient, account_mask, date_str, type_str, raw, ref_id):
        try:
            formats = ["%d-%m-%y", "%d-%m-%Y", "%d/%m/%y", "%d/%m/%Y"]
            txn_date = None
            for fmt in formats:
                try:
                    txn_date = datetime.strptime(date_str, fmt)
                    break
                except: continue
            if not txn_date: txn_date = datetime.now()
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
            raw_message=raw,
            source="SMS"
        )

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
    UPI_DEBIT_PATTERN = re.compile(
        r"(?i)(?:Rs\.?|INR)\s*([\d,]+\.?\d*)\s*has\s*been\s*debited\s*from\s*account\s*(\d+)\s*to\s*(.*?)\s*on\s*(\d{2}-\d{2}-\d{2,4})(?:.*?Ref[:\.\s]+(\w+))?",
        re.IGNORECASE
    )

    # Example: "❗ You have done a UPI txn. Rs.10.00 debited from A/c XX1234 to MERCHANT on 13-01-26. Ref: 123"
    GENERIC_UPI_PATTERN = re.compile(
        r"(?i)UPI\s*txn.*?([\d,]+\.?\d*)\s*debited\s*from\s*A/c\s*(?:.*?|x*|X*)(\d+)\s*to\s*(.*?)\s*on\s*(\d{2}-\d{2}-\d{2,4})",
        re.IGNORECASE
    )

    REF_PATTERN = re.compile(r"(?i)(?:Ref|UTR|TXN#|Ref No)[:\.\s-]+(\w{3,})")

    def can_handle(self, subject: str, body: str) -> bool:
        combined = (subject + " " + body).lower()
        # If the subject is the specific HDFC UPI alert subject, handle it
        if "you have done a upi txn" in combined:
            return True
        keywords = ["hdfc", "transaction", "debited", "spent", "txn", "upi", "vpa"]
        return any(k in combined for k in keywords)

    def parse(self, content: str) -> Optional[ParsedTransaction]:
        clean_content = " ".join(content.split())
        
        def get_ref(match, group_idx):
            if group_idx < len(match.groups()) + 1 and match.group(group_idx): 
                return match.group(group_idx)
            ref_match = self.REF_PATTERN.search(clean_content)
            return ref_match.group(1).strip() if ref_match else None

        # 1. Card
        match = self.DEBIT_CARD_PATTERN.search(clean_content)
        if match:
            return self._create_txn(Decimal(match.group(1).replace(",", "")), match.group(3), match.group(2), match.group(4), "DEBIT", content, get_ref(match, 5))

        # 2. Account
        match = self.ACCOUNT_DEBIT_PATTERN.search(clean_content)
        if match:
            return self._create_txn(Decimal(match.group(2).replace(",", "")), match.group(4), match.group(1), match.group(3), "DEBIT", content, get_ref(match, 5))

        # 3. UPI
        match = self.UPI_DEBIT_PATTERN.search(clean_content)
        if match:
            return self._create_txn(Decimal(match.group(1).replace(",", "")), match.group(3), match.group(2), match.group(4), "DEBIT", content, get_ref(match, 5))

        # 4. Generic UPI
        match = self.GENERIC_UPI_PATTERN.search(clean_content)
        if match:
            return self._create_txn(Decimal(match.group(1).replace(",", "")), match.group(3), match.group(2), match.group(4), "DEBIT", content, get_ref(match, 5))

        return None

    def _create_txn(self, amount, recipient, account_mask, date_str, type_str, raw, ref_id):
        try:
            formats = ["%d-%m-%y", "%d-%m-%Y", "%d/%m/%y", "%d/%m/%Y"]
            txn_date = None
            for fmt in formats:
                try:
                    txn_date = datetime.strptime(date_str, fmt)
                    break
                except: continue
            if not txn_date: txn_date = datetime.now()
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
            raw_message=raw,
            source="EMAIL"
        )

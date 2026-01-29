import re

class FinancialClassifier:
    
    # Keywords that suggest a financial transaction
    POSITIVE_KEYWORDS = [
        r"debited", r"credited", r"spent", r"paid", r"sent", r"received",
        r"txn", r"transaction", r"acct", r"a/c", r"bank", r"upi",
        r"withdraw", r"purchase", r"bill", r"payment"
    ]

    # Keywords that suggest noise (OTP, Promos, Notifications)
    NEGATIVE_KEYWORDS = [
        r"otp", r"login", r"password", r"verification code", 
        r"lucky winner", r"loan offer", r"apply now", r"your statement is ready",
        r"pre-approved", r"congratulations", r"cashback points", r"exclusive offer",
        r"click here", r"know more", r"vouchers", r"reward points", r"kyc update"
    ]

    @staticmethod
    def is_financial(content: str, source: str = "SMS") -> bool:
        """
        Quick heuristic check. Not 100% perfect, but filters 90% of noise.
        """
        content_lower = content.lower()
        
        # 1. Negative Check (Fast Fail)
        for kw in FinancialClassifier.NEGATIVE_KEYWORDS:
            if re.search(kw, content_lower):
                return False
        
        # 2. Positive Check
        score = 0
        for kw in FinancialClassifier.POSITIVE_KEYWORDS:
            if re.search(kw, content_lower):
                score += 1
        
        # 3. Currency Symbol Check
        if "rs." in content_lower or "inr" in content_lower:
            score += 2

        return score >= 1

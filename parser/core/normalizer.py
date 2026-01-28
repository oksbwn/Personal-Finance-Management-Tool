from typing import Optional, Dict
import re
from rapidfuzz import process, fuzz

class MerchantNormalizer:
    
    # Simple regex based aliases
    ALIASES = {
        "Amazon": [r"AMZN", r"Amazon", r"AMAZON PAY", r"AMZ\*"],
        "Swiggy": [r"SWIGGY", r"BUNDL TECHNOLOGIES"],
        "Zomato": [r"ZOMATO"],
        "Uber": [r"UBER"],
        "Ola": [r"ANI TECHNOLOGIES", r"OLA"],
        "Starbucks": [r"TATA STARBUCKS"],
        "Netflix": [r"NETFLIX"],
        "Apple": [r"APPLE\.COM", r"ITUNES"],
        "Google": [r"GOOGLE", r"GOOGLE PLAY"],
        "Reliance Fresh": [r"RELIANCE FRESH", r"RELIANCE RETAIL"],
        "BigBasket": [r"BIGBASKET", r"SUPERMARKET GROCERY"],
        "Jio": [r"RELIANCE JIO", r"JIO"],
        "Airtel": [r"BHARTI AIRTEL", r"AIRTEL"],
    }

    @staticmethod
    def normalize(raw_merchant: str) -> str:
        if not raw_merchant: 
            return "Unknown"
        
        # 1. Immediate Cleanup
        # Remove common prefixes and noise
        clean = re.sub(r"^(UPI|POS|VPS|ATW|ATM|TXN|PAY)-?", "", raw_merchant, flags=re.IGNORECASE)
        # Remove common suffixes and IDs
        clean = re.sub(r"[-/ ]\d+$", "", clean) # Trailing numbers
        clean = re.sub(r"@[A-Z0-9.\-_]{3,}", "", clean, flags=re.IGNORECASE) # VPA suffix
        clean = clean.strip()
        
        if not clean: 
            return raw_merchant.title()

        # 2. Regex Alias Lookup (High Precision)
        for clean_name, patterns in MerchantNormalizer.ALIASES.items():
            for pattern in patterns:
                if re.search(pattern, clean, re.IGNORECASE):
                    return clean_name
        
        # 3. Fuzzy Matching (Recall Helper)
        # Match against keys of ALIASES
        choices = list(MerchantNormalizer.ALIASES.keys())
        result = process.extractOne(clean, choices, scorer=fuzz.WRatio)
        
        if result and result[1] > 85: # Threshold of 85%
            return result[0]
            
        return clean.title()

import json
import hashlib
from google import genai
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal
from backend.app.modules.ingestion import models as ingestion_models
from backend.app.modules.ingestion.base import ParsedTransaction

class AIProvider(ABC):
    @abstractmethod
    def parse(self, config: ingestion_models.AIConfiguration, content: str, prompt: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_models(self, api_key: str) -> List[Dict[str, str]]:
        pass

class GeminiProvider:
    def parse(self, config: ingestion_models.AIConfiguration, content: str, prompt: str) -> Optional[Dict[str, Any]]:
        if not config.api_key:
            return None
        
        client = genai.Client(api_key=config.api_key)
        model_id = config.model_name or "gemini-1.5-flash"
        
        full_prompt = f"{prompt}\n\nTRANSACTION MESSAGE:\n{content}\n\nRESPONSE FORMAT: Single JSON object."
        
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=full_prompt
            )
            
            if not response:
                return None

            
            # Find JSON in response
            text = response.text
            
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end != 0:
                return json.loads(text[start:end])
        except Exception as e:
            # Silent fail for production ingestion or log to a proper logger
            pass
        return None

    def list_models(self, api_key: str) -> List[Dict[str, str]]:
        try:
            client = genai.Client(api_key=api_key)
            models = []
            for m in client.models.list():
                # Only include models that support content generation
                if 'generateContent' in m.supported_actions:
                    # m.name usually looks like 'models/gemini-1.5-flash'
                    # We strip 'models/' for internal consistency if needed, 
                    # but the error message showed it expecting it.
                    # Let's keep the full name as returned by the API list.
                    models.append({
                        "label": m.display_name or m.name,
                        "value": m.name
                    })
            return models
        except Exception as e:
            pass
            return []

    def generate_analysis(self, config: ingestion_models.AIConfiguration, summary_data: str) -> Optional[str]:
        if not config.api_key:
            return None
        
        client = genai.Client(api_key=config.api_key)
        model_id = config.model_name or "gemini-1.5-flash"
        
        prompt = (
            "You are a professional financial advisor. Analyze the following financial summary data for a household. "
            "Provide 3-4 concise, actionable insights or observations. Focus on spending patterns, budget health, and savings opportunities. "
            "Keep it friendly and professional. Use bullet points. "
            f"\n\nFINANCIAL SUMMARY:\n{summary_data}"
        )
        
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=prompt
            )
            return response.text if response else None
        except Exception as e:
            pass
            return None

    def generate_structured_insights(self, config: ingestion_models.AIConfiguration, summary_data: str) -> Optional[List[Dict[str, Any]]]:
        if not config.api_key:
            return None
            
        client = genai.Client(api_key=config.api_key)
        model_id = config.model_name or "gemini-1.5-flash"
        
        prompt = (
            "You are a professional financial advisor. Analyze the following financial summary data for a household. "
            "Return a JSON list of exactly 3 concise insights. Each insight must be a JSON object with: "
            "'id' (unique string), 'type' (one of: danger, warning, success, info), 'title' (short heading), "
            "'content' (1-2 sentences), 'icon' (a single emoji relevant to the topic). "
            "Focus on budget utilization, unusual spending, and income health. "
            f"\n\nFINANCIAL SUMMARY:\n{summary_data}"
        )
        
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=f"{prompt}\n\nRESPONSE FORMAT: JSON Array."
            )
            if not response or not response.text:
                return None
                
            text = response.text
            start = text.find('[')
            end = text.rfind(']') + 1
            if start != -1 and end != 0:
                return json.loads(text[start:end])
        except Exception:
            pass
        return None

    def generate_loan_advice(self, config: ingestion_models.AIConfiguration, loan_details: str) -> Optional[str]:
        if not config.api_key:
            return None
        
        client = genai.Client(api_key=config.api_key)
        model_id = config.model_name or "gemini-1.5-flash"
        
        prompt = (
            "You are a sophisticated financial planner. Analyze the following loan details provided by the user. "
            "Provide a comprehensive assessment including:\n"
            "1. Interest Rate Analysis: Is it high/low compared to current market standards (assume India region)?\n"
            "2. Prepayment Strategy: Suggest if/how they should prepay to save interest.\n"
            "3. Repayment Burden: Comment on the EMI burden if any salary info is implied (or give generic advice).\n"
            "4. Actionable Tips: Specific steps to close this loan faster.\n"
            "Format the output as clean Markdown with headers."
            f"\n\nLOAN DETAILS:\n{loan_details}"
        )
        
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=prompt
            )
            return response.text if response else None
        except Exception:
            return None

    def generate_loans_overview_advice(self, config: ingestion_models.AIConfiguration, loans_data: str) -> Optional[str]:
        if not config.api_key:
            return None
        
        client = genai.Client(api_key=config.api_key)
        model_id = config.model_name or "gemini-1.5-flash"
        
        prompt = (
            "You are a sophisticated financial planner. Analyze the following list of active loans for a household. "
            "Provide a high-level summary and strategic advice including:\n"
            "1. Portfolio Risk: Identify if they are over-leveraged or have high-interest debt mix.\n"
            "2. Consolidation Opportunities: Should they consider consolidating multiple loans?\n"
            "3. Debt Snowball/Avalanche: Which loan should they prioritize paying off first and why?\n"
            "4. Monthly Cashflow Impact: Overall impact of EMIs on their financial flexibility.\n"
            "Format the output as clean Markdown with bullet points and headers."
            f"\n\nLOANS DATA:\n{loans_data}"
        )
        
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=prompt
            )
            return response.text if response else None
        except Exception:
            return None

class AIService:
    _providers = {
        "gemini": GeminiProvider()
    }

    @classmethod
    def parse_with_ai(cls, db: Session, tenant_id: str, content: str, task: str = "parsing") -> Optional[ParsedTransaction]:
        # 1. Get Config
        config = db.query(ingestion_models.AIConfiguration).filter(
            ingestion_models.AIConfiguration.tenant_id == tenant_id,
            ingestion_models.AIConfiguration.is_enabled == True
        ).first()

        if not config:
            return None

        # 2. Check Cache
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        cached = db.query(ingestion_models.AICallCache).filter(
            ingestion_models.AICallCache.tenant_id == tenant_id,
            ingestion_models.AICallCache.content_hash == content_hash,
            ingestion_models.AICallCache.provider == config.provider
        ).first()

        if cached:
            return cls._map_to_parsed(json.loads(cached.response_json), content)

        # 3. Call LLM
        provider = cls._providers.get(config.provider.lower())
        if not provider:
            return None

        prompts = json.loads(config.prompts_json or "{}")
        default_prompt = (
            "You are a financial parsing expert. Analyze the following message and determine if it describes a financial transaction "
            "(like an expense, credit, bank transfer, bill payment, etc.). "
            "Return a JSON object with the following keys:\n"
            "- 'is_transaction': Set to false if it is NOT a transaction (e.g., login alert, OTP, promotional email), otherwise true.\n"
            "- 'amount': number (absolute value)\n"
            "- 'date': DD/MM/YYYY\n"
            "- 'recipient': string (merchant name)\n"
            "- 'account_mask': 4 digits\n"
            "- 'ref_id': string or null\n"
            "- 'type': DEBIT or CREDIT\n"
            "- 'balance': number or null\n"
            "- 'credit_limit': number or null"
        )
        prompt = prompts.get(task, default_prompt)

        result = provider.parse(config, content, prompt)

        if result:
            # Check if AI explicitly marked it as non-transactional
            if result.get("is_transaction") is False:
                return None
            
            # Additional safety: if amount is 0 and it's not a known special case, skip
            if result.get("amount") == 0 and not result.get("is_transfer"):
                 return None

            # 4. Store in Cache
            new_cache = ingestion_models.AICallCache(
                tenant_id=tenant_id,
                content_hash=content_hash,
                provider=config.provider,
                model_name=config.model_name or "unknown",
                response_json=json.dumps(result)
            )
            db.add(new_cache)
            db.commit()
            
            return cls._map_to_parsed(result, content)

        return None

    @staticmethod
    def _map_to_parsed(data: Dict[str, Any], raw_message: str) -> ParsedTransaction:
        # Robust number parsing
        amt = data.get("amount", 0)
        if isinstance(amt, str):
            amt = amt.replace(",", "")
        
        # Robust date parsing
        txn_date = datetime.now()
        date_str = data.get("date")
        if date_str:
            for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]:
                try:
                    txn_date = datetime.strptime(date_str, fmt)
                    break
                except: continue

        return ParsedTransaction(
            amount=Decimal(str(amt)),
            date=txn_date,
            description=f"AI: {data.get('recipient', 'Unknown')}",
            type=data.get("type", "DEBIT").upper(),
            account_mask=str(data.get("account_mask", "XXXX"))[-4:],
            recipient=data.get("recipient"),
            balance=Decimal(str(data.get("balance"))) if data.get("balance") is not None else None,
            credit_limit=Decimal(str(data.get("credit_limit"))) if data.get("credit_limit") is not None else None,
            ref_id=data.get("ref_id"),
            raw_message=raw_message,
            source="AI_LLM", # Or pass original source
            is_ai_parsed=True
        )

    @classmethod
    def list_available_models(cls, db: Session, tenant_id: str, provider_name: str, api_key_override: Optional[str] = None) -> List[Dict[str, str]]:
        # 1. Get API Key (either from override or DB)
        api_key = api_key_override
        if not api_key:
            config = db.query(ingestion_models.AIConfiguration).filter(
                ingestion_models.AIConfiguration.tenant_id == tenant_id
            ).first()
            if config:
                api_key = config.api_key
        
        if not api_key:
            return []

        # 2. Call Provider
        provider = cls._providers.get(provider_name.lower())
        if not provider:
            return []
            
        return provider.list_models(api_key)

    @classmethod
    def generate_summary_insights(cls, db: Session, tenant_id: str, summary_data: Dict[str, Any]) -> Optional[str]:
        # 1. Get Config
        config = db.query(ingestion_models.AIConfiguration).filter(
            ingestion_models.AIConfiguration.tenant_id == tenant_id,
            ingestion_models.AIConfiguration.is_enabled == True
        ).first()

        if not config:
            return "AI Insights are currently disabled in settings."

        # 2. Call Provider
        provider = cls._providers.get(config.provider.lower())
        if not provider or not hasattr(provider, 'generate_analysis'):
            return "AI Provider not configured correctly."

        # Convert summary to string for the prompt
        summary_str = json.dumps(summary_data, indent=2)
        
        return provider.generate_analysis(config, summary_str)

    @classmethod
    def generate_structured_insights(cls, db: Session, tenant_id: str, summary_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        # 1. Get Config
        config = db.query(ingestion_models.AIConfiguration).filter(
            ingestion_models.AIConfiguration.tenant_id == tenant_id,
            ingestion_models.AIConfiguration.is_enabled == True
        ).first()

        if not config:
            return None

        # 2. Call Provider
        provider = cls._providers.get(config.provider.lower())
        if not provider or not hasattr(provider, 'generate_structured_insights'):
            return None

        # Convert summary to string for the prompt
        summary_str = json.dumps(summary_data, indent=2)
        
        return provider.generate_structured_insights(config, summary_str)

    @classmethod
    def generate_loan_insights(cls, db: Session, tenant_id: str, loan_data: Dict[str, Any]) -> Optional[str]:
        # 1. Get Config
        config = db.query(ingestion_models.AIConfiguration).filter(
            ingestion_models.AIConfiguration.tenant_id == tenant_id,
            ingestion_models.AIConfiguration.is_enabled == True
        ).first()

        if not config:
            return "AI Insights are currently disabled in settings."

        # 2. Call Provider
        provider = cls._providers.get(config.provider.lower())
        if not provider or not hasattr(provider, 'generate_loan_advice'):
            return "AI Provider not configured correctly."

        # Convert summary to string for the prompt
        details_str = json.dumps(loan_data, indent=2)
        
        return provider.generate_loan_advice(config, details_str)

    @classmethod
    def generate_loans_overview_insights(cls, db: Session, tenant_id: str, loans_data: List[Dict[str, Any]]) -> Optional[str]:
        # 1. Get Config
        config = db.query(ingestion_models.AIConfiguration).filter(
            ingestion_models.AIConfiguration.tenant_id == tenant_id,
            ingestion_models.AIConfiguration.is_enabled == True
        ).first()

        if not config:
            return "AI Insights are currently disabled in settings."

        # 2. Call Provider
        provider = cls._providers.get(config.provider.lower())
        if not provider or not hasattr(provider, 'generate_loans_overview_advice'):
            return "AI Provider not configured correctly."

        # Convert summary to string for the prompt
        data_str = json.dumps(loans_data, indent=2)
        
        return provider.generate_loans_overview_advice(config, data_str)

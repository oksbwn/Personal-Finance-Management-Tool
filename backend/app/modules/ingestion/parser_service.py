import requests
from typing import Optional, Dict, Any, List
from backend.app.core.config import settings

class ExternalParserService:
    @staticmethod
    def parse_sms(sender: str, body: str) -> Optional[Dict[str, Any]]:
        """
        Call the external parser microservice for SMS ingestion.
        """
        try:
            url = f"{settings.PARSER_SERVICE_URL}/ingest/sms"
            # Parser expects 'sender' and 'body'
            payload = {"sender": sender, "body": body}
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error calling external parser: {e}")
            return None

    @staticmethod
    def parse_email(subject: str, body_text: str, sender: str = "Unknown") -> Optional[Dict[str, Any]]:
        """
        Call the external parser microservice for Email ingestion.
        """
        try:
            url = f"{settings.PARSER_SERVICE_URL}/ingest/email"
            # Parser expects 'subject', 'body_text', 'sender'
            payload = {
                "subject": subject, 
                "body_text": body_text,
                "sender": sender
            }
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error calling external parser: {e}")
            return None

    @staticmethod
    def sync_ai_config(api_key: str, model_name: str, is_enabled: bool):
        """
        Push AI configuration to the microservice.
        """
        try:
            url = f"{settings.PARSER_SERVICE_URL}/config/ai"
            payload = {
                "api_key": api_key,
                "model_name": model_name,
                "is_enabled": is_enabled
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Error syncing AI config: {e}")
            return False

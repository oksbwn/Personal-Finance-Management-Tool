from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from backend.app.modules.ingestion.base import BaseSmsParser, BaseEmailParser, ParsedTransaction

class SmsParserRegistry:
    _parsers: List[BaseSmsParser] = []

    @classmethod
    def register(cls, parser: BaseSmsParser):
        """Register a new parser instance."""
        cls._parsers.append(parser)

    @classmethod
    def parse(cls, db: Session, tenant_id: str, sender: str, message: str) -> Optional[ParsedTransaction]:
        """
        Iterate through registered parsers, then check user-defined patterns, then AI.
        """
        # 1. Try static parsers
        for parser in cls._parsers:
            if parser.can_handle(sender, message):
                res = parser.parse(message)
                if res: return res
        
        # 2. Try User-Defined Patterns
        from backend.app.modules.ingestion.parsers.pattern_parser import PatternParser
        res = PatternParser.parse(db, tenant_id, message, "SMS")
        if res: return res

        # 3. Try AI Parsing (Gemini/LLM)
        from backend.app.modules.ingestion.ai_service import AIService
        return AIService.parse_with_ai(db, tenant_id, message, "parsing")

class EmailParserRegistry:
    _parsers: List[BaseEmailParser] = []

    @classmethod
    def register(cls, parser: BaseEmailParser):
        """Register a new parser instance."""
        cls._parsers.append(parser)

    @classmethod
    def parse(cls, subject: str, body: str, db: Session, tenant_id: str, date_hint: Optional[datetime] = None) -> Optional[ParsedTransaction]:
        """
        Iterate through registered parsers, then check user-defined patterns.
        """
        # Combine subject and body for matching and parsing
        combined_content = f"Subject: {subject}\nBody: {body}"
        
        # 1. Try static parsers
        for parser in cls._parsers:
            if parser.can_handle(subject, body):
                # Pass combined content to static parsers as well
                res = parser.parse(combined_content, date_hint)
                if res: return res
        
        # 2. Try User-Defined Patterns
        from backend.app.modules.ingestion.parsers.pattern_parser import PatternParser
        res = PatternParser.parse(db, tenant_id, combined_content, "EMAIL", date_hint)
        if res: return res

        # 3. Try AI Parsing (Gemini/LLM) as final fallback
        from backend.app.modules.ingestion.ai_service import AIService
        return AIService.parse_with_ai(db, tenant_id, combined_content, "parsing")

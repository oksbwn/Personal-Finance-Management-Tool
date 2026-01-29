from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import json

from parser.db.database import get_db
from parser.core.pipeline import IngestionPipeline
from parser.schemas.transaction import IngestionResult, ParsedItem, TransactionMeta
from parser.parsers.bank.hdfc import HdfcSmsParser, HdfcEmailParser
from parser.parsers.bank.icici import IciciSmsParser, IciciEmailParser
from parser.parsers.bank.sbi import SbiSmsParser, SbiEmailParser
from parser.parsers.bank.axis import AxisSmsParser
from parser.parsers.bank.kotak import KotakSmsParser
from parser.parsers.bank.generic import GenericSmsParser
from parser.parsers.registry import ParserRegistry
from parser.parsers.file.universal_parser import UniversalParser
from parser.parsers.cas.cas_parser import CasParser
from parser.db.models import FileParsingConfig

# Register SMS Parsers
ParserRegistry.register_sms(HdfcSmsParser())
ParserRegistry.register_sms(IciciSmsParser())
ParserRegistry.register_sms(SbiSmsParser())
ParserRegistry.register_sms(AxisSmsParser())
ParserRegistry.register_sms(KotakSmsParser())
ParserRegistry.register_sms(GenericSmsParser())

# Register Email Parsers
ParserRegistry.register_email(HdfcEmailParser())
ParserRegistry.register_email(IciciEmailParser())
ParserRegistry.register_email(SbiEmailParser())

router = APIRouter(prefix="/v1/ingest", tags=["Ingestion"])

class SmsIngestRequest(BaseModel):
    sender: str
    body: str
    received_at: Optional[str] = None

class EmailIngestRequest(BaseModel):
    subject: str
    body_text: str
    sender: str
    received_at: Optional[str] = None

@router.post("/sms", response_model=IngestionResult)
def ingest_sms(
    payload: SmsIngestRequest,
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    pipeline = IngestionPipeline(db)
    result = pipeline.run(payload.body, "SMS", payload.sender)
    return result

@router.post("/email", response_model=IngestionResult)
def ingest_email(
    payload: EmailIngestRequest,
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    pipeline = IngestionPipeline(db)
    result = pipeline.run(payload.body_text, "EMAIL", sender=payload.sender, subject=payload.subject)
    return result

@router.post("/file", response_model=IngestionResult)
async def ingest_file(
    file: UploadFile = File(...),
    account_fingerprint: Optional[str] = Form(None),
    mapping_override: Optional[str] = Form(None), 
    header_row_index: Optional[int] = Form(None),
    password: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    
    
    content = await file.read()
    filename = file.filename
    
    mapping = {}
    header_idx = header_row_index or 0
    
    if account_fingerprint:
        saved = db.query(FileParsingConfig).filter(FileParsingConfig.fingerprint == account_fingerprint).first()
        if saved:
            mapping = saved.columns_json
            if header_row_index is None:
                header_idx = saved.header_row_index
            
    if mapping_override:
        try:
             mapping = json.loads(mapping_override)
        except: pass

    if not mapping:
        try:
            analysis = UniversalParser.analyze(content, filename)
            return IngestionResult(status="analysis_required", results=[], logs=["No mapping found. Analysis: " + json.dumps(analysis, default=str)])
        except Exception as e:
            return IngestionResult(status="failed", results=[], logs=[str(e)])

    try:
        raw_txns, skipped_logs = UniversalParser.parse(content, filename, mapping, header_idx, password=password)
        pipeline = IngestionPipeline(db)
        results = []
        for t_dict in raw_txns:
            t = pipeline._convert_to_schema_txn(t_dict)
            results.append(ParsedItem(
                status="extracted",
                transaction=t,
                metadata=TransactionMeta(confidence=1.0, parser_used="UniversalParser", source_original="FILE")
            ))
        
        status = "success" if results else "failed"
        if not results and skipped_logs:
             # If no results but we have skipped logs, return them
             return IngestionResult(status="failed", results=[], logs=skipped_logs)
             
        return IngestionResult(status=status, results=results, logs=skipped_logs)
    except Exception as e:
        return IngestionResult(status="failed", results=[], logs=[str(e)])

@router.post("/cas")
async def ingest_cas(
    file: UploadFile = File(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    
    content = await file.read()
    try:
        data = CasParser.parse(content, password)
        return {"status": "success", "count": len(data), "transactions": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CAS Parse Failed: {str(e)}")

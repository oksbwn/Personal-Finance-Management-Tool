# Parser Microservice

A production-ready microservice for parsing financial transactions from various sources (SMS, Email, Files, CAS statements).

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the service:
```bash
python main.py
```
Or with uvicorn direct:
```bash
uvicorn parser.main:app --host 0.0.0.0 --port 8001 --reload
```

## API Docs
Once running, visit: http://localhost:8001/docs

## Architecture
- **Port**: 8001
- **DB**: Local DuckDB (`ingestion_engine.duckdb`)
- **Parsers**: Located in `parser/parsers/`

# Parser Microservice

A production-ready microservice for parsing financial transactions from various sources (SMS, Email, Files, CAS statements). This service leverages the perfected parsing logic from the main application, now encapsulated in a standalone, scalable microservice.

## ✨ Features

- **Multi-Source Parsing**: Support for SMS, Email, and File-based (CSV/Excel) transaction ingestion.
- **Bank-Specific Robustness**: Includes refined parsers for HDFC, SBI, ICICI, Axis, Kotak, and more.
- **AI-Powered Fallback**: Uses Google Gemini for complex or non-standard messages.
- **User-Trainable Patterns**: Dynamic regex-based parsing rules configurable via API.
- **Advanced Robustness**:
    - **Cross-Source Deduplication**: Automatically detects if an SMS and Email represent the same transaction within a 15-minute window.
    - **Fuzzy Merchant Normalization**: Uses Levenshtein distance (rapidfuzz) to group similar merchant names (e.g., "AMZ*PAY" → "Amazon").
    - **Financial Classification**: Automatically filters out OTPs and promotional spam.
- **Monitoring & Analytics**: Built-in `/v1/stats` endpoint to track parser performance and status breakdowns.
- **Mutual Fund CAS Support**: PDF statement parsing for CAMS/Karvy Consolidated Account Statements.

## 🛠 Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the service**:
   ```bash
   python main.py
   ```
   The service will start on **port 8001** and initialize a local DuckDB database.

## 📁 Repository Structure

- `parser/api`: Categorized FastAPI routers.
    - `system.py`: Health checks and diagnostic endpoints.
    - `ingestion.py`: SMS, Email, and File upload endpoints.
    - `config.py`: AI, Pattern, and File mapping configurations.
    - `analytics.py`: Usage stats, performance monitoring, and history logs.
- `parser/core`: The central ingestion pipeline, classifier, normalizer, and validator.
- `parser/parsers`:
    - `bank/`: Perfectioned static parsers for Indian banks (SMS & Email).
    - `ai/`: Gemini-powered LLM parsing logic.
    - `patterns/`: Dynamic regex engine for user-defined rules.
    - `universal.py`: Smart CSV/Excel parser with auto-header detection.
- `parser/db`: SQLAlchemy models and DuckDB configuration.
- `parser/tests`: Comprehensive integration and robustness test suite.

## 🧪 Testing

Run the integration tests to verify all parsers and the pipeline:
```bash
python parser/tests/test_integration.py
```
Or test robustness features:
```bash
python parser/tests/test_robustness.py
```

## 📖 API Documentation

Once the service is running, explore the interactive API documentation at:
**[http://localhost:8001/docs](http://localhost:8001/docs)**

---
*Maintained by the Antigravity Team*

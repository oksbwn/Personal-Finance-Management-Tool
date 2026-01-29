import duckdb
import json
import os

db_path = "c:\\Users\\oksbw\\.gemini\\antigravity\\scratch\\data\\ingestion_engine_parser.duckdb"
if not os.path.exists(db_path):
    print(f"File not found: {db_path}")
    exit(1)

try:
    con = duckdb.connect(db_path, read_only=True)
    res = con.execute("SELECT id, source, status, output_payload, created_at FROM request_logs ORDER BY created_at DESC LIMIT 10").fetchall()
    for row in res:
        id_val, source, status, payload, created_at = row
        print(f"ID: {id_val} | Source: {source} | Status: {status} | Time: {created_at}")
        if payload:
            p = json.loads(payload)
            if "error" in p:
                print(f"  Error: {p['error']}")
            elif "logs" in p and p["logs"]:
                print(f"  Logs: {p['logs']}")
        print("-" * 40)
    con.close()
except Exception as e:
    print(f"Error: {e}")

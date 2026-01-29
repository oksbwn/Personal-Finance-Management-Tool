import requests
import json

try:
    response = requests.get("http://localhost:8001/v1/logs?limit=5")
    if response.status_code == 200:
        logs = response.json().get("logs", [])
        for log in logs:
            print(f"ID: {log['id']} | Source: {log['source']} | Status: {log['status']}")
            payload = log.get("output_payload")
            if payload:
                if isinstance(payload, str):
                    payload = json.loads(payload)
                if "error" in payload:
                    print(f"  Error: {payload['error']}")
                elif "logs" in payload and payload["logs"]:
                    print(f"  Logs: {payload['logs']}")
            print("-" * 40)
    else:
        print(f"Failed to fetch logs: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Error: {e}")

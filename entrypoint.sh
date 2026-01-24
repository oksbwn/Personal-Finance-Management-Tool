#!/bin/bash

# Start Nginx in background
nginx

# Start Backend
# Note: We run the python script which starts uvicorn. 
# In production, we might want to override the host/port if needed, 
# but run_backend.py defaults to 127.0.0.1:8000 which works with our Nginx proxy.
python run_backend.py

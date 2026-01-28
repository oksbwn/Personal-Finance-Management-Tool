import uvicorn
import os
import sys
import multiprocessing
import time

# Ensure the current directory (project root) is in sys.path
sys.path.append(os.getcwd())

def run_main_app():
    print("Starting Main Backend on port 8000...")
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=False)

def run_parser_service():
    print("Starting Parser Service on port 8001...")
    # Parser needs its own DB path config usually, handled by env vars
    uvicorn.run("parser.main:app", host="0.0.0.0", port=8001, reload=False)

if __name__ == "__main__":
    # simple process manager
    p1 = multiprocessing.Process(target=run_main_app)
    p2 = multiprocessing.Process(target=run_parser_service)

    p1.start()
    p2.start()

    try:
        p1.join()
        p2.join()
    except KeyboardInterrupt:
        print("Stopping services...")
        p1.terminate()
        p2.terminate()

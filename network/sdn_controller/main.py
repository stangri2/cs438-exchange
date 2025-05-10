from fastapi import FastAPI, HTTPException
import json
import os
from typing import Dict, List, Optional
import logging
import uvicorn

# Setuplogging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SDN Controller API")

ROUTER_TABLES_DIR = "/shared/"

@app.get("/sdn_controller/health")
def service_health():
    return {
        "status": "running", 
        "service": "SDN Controller"
    }

@app.get("/sdn_controller/routers/flow_table/{router_id}")
def get_flow_table(router_id: str):
    file_path = os.path.join(ROUTER_TABLES_DIR, f"{router_id}_table.json")
    try:
        with open(file_path, "r") as file:
            router_data = json.load(file)
    except FileNotFoundError:
        logger.error(f"Table for router {router_id} not found")
        return {
            "router_id": router_id,
            "flow_table": [],
            "interfaces": {}
        }
    return router_data['flow_table']

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
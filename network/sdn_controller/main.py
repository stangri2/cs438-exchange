from fastapi import FastAPI, HTTPException
import json
import os
from typing import Dict, List, Optional
import logging

# Setup logging
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
    # first read the shared folder to access the file
    file_path = os.path.join(ROUTER_TABLES_DIR, f"{router_id}_table.json")
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        logger.error(f"Table for router {router_id} not found")
        return {
            "router_id": router_id,
            "flow_table": [],
            "interfaces": {}
        }
    # except json.JSONDecodeError:
    #     logger.error(f"Invalid JSON in table for router {router_id}")
    #     raise HTTPException(status_code=500, detail=f"Invalid JSON in router table for {router_id}")

    return {
        "router_id": router_id,
        "flow_table": table.get("flow_table", [])
    }

@app.get("/routers")
def list_routers():
    """List all routers with available tables."""
    router_ids = []
    
    for filename in os.listdir(ROUTER_TABLES_DIR):
        if filename.endswith("_table.json"):
            router_id = filename.replace("_table.json", "")
            router_ids.append(router_id)
    
    return {"routers": router_ids}

@app.get("/routers/{router_id}")
def get_router_info(router_id: str):
    """Get information about a specific router."""
    table = get_router_table(router_id)
    
    return {
        "router_id": router_id,
        "interfaces": table.get("interfaces", {}),
        "flow_entries": len(table.get("flow_table", []))
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
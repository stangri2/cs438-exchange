from fastapi import FastAPI, HTTPException
import json
import os
from typing import Dict, List, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SDN Controller API")

# Configuration
ROUTER_TABLES_DIR = "/shared/routerA_table.json"  # Directory for router tables (shared volume)

# Ensure the directory exists
os.makedirs(ROUTER_TABLES_DIR, exist_ok=True)

def get_router_table(router_id: str) -> Dict:
    """Read a router's flow table from the shared volume."""
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
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in table for router {router_id}")
        raise HTTPException(status_code=500, detail=f"Invalid JSON in router table for {router_id}")

def save_router_table(router_id: str, table: Dict) -> None:
    """Save a router's flow table to the shared volume."""
    file_path = os.path.join(ROUTER_TABLES_DIR, f"{router_id}_table.json")
    
    with open(file_path, "w") as file:
        json.dump(table, file, indent=2)
    
    logger.info(f"Saved table for router {router_id}")

@app.get("/")
def read_root():
    return {"status": "running", "service": "SDN Controller"}

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
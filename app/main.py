from fastapi import FastAPI
import uvicorn
from uuid import uuid4
import sys
import os
from fastapi.middleware.cors import CORSMiddleware

# Add the parent directory to sys.path to allow importing from dnd package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import entity registry and entities
from dnd.entity import Entity
from dnd.monsters.circus_fighter import create_warrior

# Import API routers
from app.api.routes.entities import router as entities_router
from app.api.routes.equipment import router as equipment_router

# Create FastAPI application
app = FastAPI(
    title="DnD Engine API", 
    description="API for accessing the DnD Engine entity registry",
    version="0.1.0"
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React app origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(entities_router, prefix="/api")
app.include_router(equipment_router, prefix="/api")

# Initialize test entities
@app.on_event("startup")
def initialize_test_entities():
    """Create test entities on startup"""
    # Create a warrior from circus_fighter.py
    warrior_uuid = uuid4()
    warrior = create_warrior(source_id=warrior_uuid, proficiency_bonus=2, name="Test Warrior")
    
    # Create a second entity for testing
    rogue_uuid = uuid4()
    rogue = create_warrior(source_id=rogue_uuid, proficiency_bonus=3, name="Test Rogue")
    
    print(f"Created test entities with UUIDs:")
    print(f"- Test Warrior: {warrior_uuid}")
    print(f"- Test Rogue: {rogue_uuid}")

# Run the app with uvicorn
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 
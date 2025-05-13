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
from dnd.core.events import EventQueue
from dnd.monsters.circus_fighter import create_warrior
from dnd.core.base_tiles import floor_factory, wall_factory, water_factory

# Import API routers
from app.api.routes.entities import router as entities_router
from app.api.routes.equipment import router as equipment_router
from app.api.routes.events import router as events_router
from app.api.routes.tiles import router as tiles_router

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
app.include_router(events_router, prefix="/api")
app.include_router(tiles_router, prefix="/api")

# Initialize test entities
@app.on_event("startup")
def initialize_test_entities():
    """Create test entities on startup"""
    q=EventQueue()
    
    # Create a warrior from circus_fighter.py
    warrior_uuid = uuid4()
    warrior = create_warrior(source_id=warrior_uuid, proficiency_bonus=2, name="Spiky Clown", position=(16,8),sprite_name="death_knight.png")
    
    # Create a second entity for testing
    rogue_uuid = uuid4()
    blinded_rogue = create_warrior(source_id=rogue_uuid, proficiency_bonus=3, name="Blinded Pirate",blinded=True, position=(17,9),sprite_name="deep_elf_fighter_new.png")
    warrior.senses.add_entity(rogue_uuid,blinded_rogue.senses.position)
    
    blinded_rogue.senses.add_entity(warrior_uuid,warrior.senses.position)
    warrior.set_target_entity(blinded_rogue.uuid)
    blinded_rogue.set_target_entity(warrior.uuid)
    print(f"Created test entities with UUIDs:")
    print(f"- Test Warrior: {warrior_uuid} with target {warrior.target_entity_uuid}")
    print(f"- Test Rogue: {rogue_uuid} with target {blinded_rogue.target_entity_uuid}")
    floor_16_8 = floor_factory((16,8))
    floor_17_9 = floor_factory((17,9))
    floor_16_9 = floor_factory((16,9))
    floor_17_8 = floor_factory((17,8))
    wall_25_25 = wall_factory((32,32))
# Run the app with uvicorn
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 
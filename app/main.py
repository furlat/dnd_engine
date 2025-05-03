from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uuid import UUID

# Import the endpoints
from app.api.endpoints import values

# For testing, let's import and create a sample entity
from dnd.monsters.circus_fighter import create_warrior
from uuid import uuid4

app = FastAPI(
    title="D&D Engine API",
    description="API for the D&D 5e game engine",
    version="0.1.0",
)

# Add CORS middleware for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the routers
app.include_router(values.router, prefix="/api", tags=["values"])

# Create a sample entity on startup for testing
@app.on_event("startup")
async def startup_event():
    # Create a sample entity
    source_id = uuid4()
    proficiency_bonus = 2
    entity = create_warrior(source_id, proficiency_bonus, name="Sample Warrior")
    print(f"Created sample entity with UUID: {source_id}")
    print(f"entities attack bonus uuid: {entity.equipment.attack_bonus.uuid} with score: {entity.equipment.attack_bonus.normalized_score}")
    print(f"entities normalized strenght score uuid: {entity.ability_scores.strength.ability_score.uuid} with score: {entity.ability_scores.strength.ability_score.normalized_score}")
@app.get("/")
async def root():
    return {"message": "Welcome to the D&D Engine API"}
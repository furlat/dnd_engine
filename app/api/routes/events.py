# app/api/routes/events.py
from fastapi import APIRouter, HTTPException, Query, Path
from typing import List, Optional
from uuid import UUID

from dnd.core.events import EventQueue, WeaponSlot
from dnd.actions import Attack
from dnd.entity import Entity
from app.models.events import EventSnapshot

router = APIRouter(
    prefix="/events",
    tags=["events"],
    responses={404: {"description": "Event not found"}},
)

@router.get("/{event_uuid}", response_model=EventSnapshot)
async def get_event_by_uuid(
    event_uuid: UUID,
    include_children: bool = Query(False, description="Whether to include child events in the response")
):
    """Get a specific event by its UUID"""
    event = EventQueue.get_event_by_uuid(event_uuid)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return EventSnapshot.from_engine(event, include_children=include_children)

@router.get("/lineage/{lineage_uuid}", response_model=List[EventSnapshot])
async def get_events_by_lineage(
    lineage_uuid: UUID,
    include_children: bool = Query(False, description="Whether to include child events in the response")
):
    """Get all events with a specific lineage UUID"""
    events = EventQueue.get_event_history(lineage_uuid)
    if not events:
        raise HTTPException(status_code=404, detail="No events found for this lineage")
    
    return [EventSnapshot.from_engine(event, include_children=include_children) for event in events]

@router.get("/latest/{count}", response_model=List[EventSnapshot])
async def get_latest_events(
    count: int = Path(..., description="Number of latest events to return", gt=0),
    include_children: bool = Query(False, description="Whether to include child events in the response")
):
    """Get the latest K events"""
    events = EventQueue.get_latest_events(count)
    
    if not include_children:
        # Simple case - just return the last K events without children
        return [EventSnapshot.from_engine(event, include_children=False) for event in events]
    
    # When including children, we need to handle parent-child relationships carefully
    # to avoid duplicates while maintaining the parent-child structure
    seen_uuids = set()
    result = []
    
    for event in events:
        if event.uuid not in seen_uuids:
            # Create snapshot with children
            snapshot = EventSnapshot.from_engine(event, include_children=True)
            
            # Add all child UUIDs to seen set to avoid duplicates
            def collect_child_uuids(event_snapshot):
                seen_uuids.add(event_snapshot.uuid)
                for child in event_snapshot.child_events:
                    collect_child_uuids(child)
            
            collect_child_uuids(snapshot)
            result.append(snapshot)
    
    return result

@router.post("/entity/{entity_uuid}/attack/{target_uuid}", response_model=EventSnapshot)
async def execute_attack(
    entity_uuid: UUID,
    target_uuid: UUID,
    weapon_slot: WeaponSlot = Query(WeaponSlot.MAIN_HAND, description="Which weapon slot to use for the attack"),
    attack_name: str = Query("Attack", description="Name of the attack")
):
    """Execute an attack from one entity to another"""
    entity = Entity.get(entity_uuid)
    target = Entity.get(target_uuid)
    
    if not entity:
        raise HTTPException(status_code=404, detail="Source entity not found")
    if not target:
        raise HTTPException(status_code=404, detail="Target entity not found")
    
    # Create and execute the attack
    attack = Attack(
        name=attack_name,
        source_entity_uuid=entity_uuid,
        target_entity_uuid=target_uuid,
        weapon_slot=weapon_slot
    )
    
    result_event = attack.apply()
    if not result_event:
        raise HTTPException(status_code=400, detail="Attack could not be executed")
        
    return EventSnapshot.from_engine(result_event, include_children=True) 
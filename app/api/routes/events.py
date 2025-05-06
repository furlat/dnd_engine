# app/api/routes/events.py
from fastapi import APIRouter, HTTPException, Query, Path
from typing import List, Optional
from uuid import UUID

from dnd.core.events import EventQueue
from dnd.interfaces.events import EventSnapshot

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
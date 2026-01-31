# Terrain and 3D Spatial Systems - Future Plan

This document outlines systems deferred from the AoE implementation, to be implemented together as a unified "3D Spatial System".

## Deferred Systems

### 1. Terrain Effects

Ground hazards, difficult terrain, tile conditions:
- **Difficult Terrain**: Half movement speed
- **Hazard Tiles**: Fire (Web + Fire), Acid, Spike Growth damage
- **Area Conditions**: Fog Cloud (heavily obscured), Web (restrained), Entangle, Spike Growth, Wall of Fire

**Requires:**
- Tile condition system (tiles already have `conditions` field from BaseBlock)
- Spatial event handlers (SPATIAL_ENTITY_ENTERED already exists)
- Cost modifiers for difficult terrain in pathfinding

### 2. Movement Modes

Swimming, Burrowing, Flying - alternative movement types:
- **Swim Speed**: Water movement without exhaustion/drowning
- **Burrow Speed**: Underground movement through earth
- **Fly Speed**: 3D movement, hovering, Fly spell

**Requires:**
- Terrain type enum (FLOOR, WALL, WATER, AIR, EARTH)
- Movement mode tracking per entity
- 3D pathfinding for flying
- Spells: Water Breathing, Water Walk, Fly, Levitate

### 3. Light System

Darkness levels and vision interactions:
- **Light Levels**: Bright → Dim → Darkness → Magical Darkness
- **Darkvision**: Treat darkness as dim light within range
- **Low-light Vision**: Extended dim light range
- **See Invisibility**: Override invisibility condition

**Requires:**
- Light level per tile
- Light source tracking (torches, Light cantrip, Daylight spell)
- Vision type on entities (normal, darkvision 60ft, etc.)
- Invisibility interaction with See Invisibility

### 4. Hiding and Stealth

Concealment and invisibility mechanics:
- **Hiding**: Stealth vs Perception
- **Concealment**: Lightly/Heavily obscured areas
- **Invisibility**: Auto-hide, attack reveals

**Requires:**
- Obscurement level per tile (from fog, darkness, foliage)
- Hidden state tracking
- Stealth contest mechanics
- Reveals on attack/spell

### 5. Cover System

Obstacles providing AC bonus:
- **Half Cover**: +2 AC, +2 DEX saves
- **Three-Quarters Cover**: +5 AC, +5 DEX saves
- **Full Cover**: Cannot be targeted

**Requires:**
- Cover calculation from tile geometry
- Raycasting to determine cover level
- Cover objects (barriers, walls, creatures)

### 6. Z-Axis / Verticality

True 3D combat:
- **Elevation**: Height differences affecting range/cover
- **Flying**: 3D movement and pathfinding
- **Vertical Spells**: Reverse Gravity, Levitate, Fly
- **Fall Damage**: 1d6 per 10ft

**Requires:**
- Z coordinate for positions
- 3D FOV calculation (shadowcast extension)
- 3D pathfinding (Dijkstra with vertical neighbors)
- Fall detection on movement
- ASCII visualization for 3D (side view? layers?)

## Why Implement Together

These systems are interconnected:

```
Light System ─────► Hiding ─────► Cover
     │                 │            │
     ▼                 ▼            ▼
Darkvision ───► Stealth ────► AC Bonus
     │                              │
     └──────────────────────────────┘
              Spatial Effects

Terrain Effects ────► Movement Modes ────► Z-Axis
     │                      │                 │
     ▼                      ▼                 ▼
Tile Conditions ───► Fly/Swim ────► 3D Pathfinding
```

**Specific Dependencies:**
- Cover requires raycasting → benefits from Z-axis raycasting
- Hiding requires obscurement → Light system provides this
- Flying requires Z-axis → Z-axis enables falling damage
- Terrain effects require tile conditions → same system for hazards and light sources

## Implementation Priority (When Done)

1. **Tile Conditions** - Foundation for everything else
2. **Light System** - Enables obscurement and darkvision
3. **Cover** - Common combat mechanic
4. **Hiding/Stealth** - Uses light + cover
5. **Z-Axis** - Major architectural change
6. **Movement Modes** - Uses Z-axis for fly

## Spells Waiting on These Systems

| Spell | System Needed |
|-------|---------------|
| Fog Cloud | Terrain (heavily obscured area) |
| Web | Terrain (restrained + flammable) |
| Wall of Fire | Terrain (damage zone) |
| Cloudkill | Terrain (moving poison cloud) |
| Entangle | Terrain (restrained area) |
| Spike Growth | Terrain (damage on movement) |
| Darkness | Light system |
| Faerie Fire | Light system (outline, no invis) |
| See Invisibility | Light system |
| Fly | Z-axis + movement mode |
| Levitate | Z-axis |
| Reverse Gravity | Z-axis |
| Water Breathing | Movement mode |

## Current Spatial Capabilities

Already implemented and working:
- 2D grid with wall blocking
- FOV (shadowcast algorithm)
- Pathfinding (Dijkstra)
- Spatial events (ENTERED, LEFT, CHANGED)
- AoE shapes (Sphere, Cone, Line, Cube)
- Entity position tracking
- Tile types (Floor, Wall, Water)

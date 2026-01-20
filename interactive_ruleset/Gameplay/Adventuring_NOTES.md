# Adventuring.md - Implementation Notes

## Status: PARTIAL - Key systems missing for full combat loop

This file covers time, movement, environment, and resting. Critical for understanding the combat loop timing.

---

## Key Insight: Time Scales

The SRD defines four time scales:
| Scale | Use Case | Duration |
|-------|----------|----------|
| **Rounds** | Combat | 6 seconds |
| Minutes | Dungeon exploration | - |
| Hours | City/wilderness travel | - |
| Days | Long journeys | - |

**For combat, everything happens in ROUNDS of 6 seconds each.**

---

## Implemented

### Basic Movement
- Speed as ModifiableValue (default 30ft)
- Path computation via Dijkstra (`gridmap.py`)
- Movement cost deduction from ActionEconomy
- Path validation before movement

### FOV/Visibility
- Shadowcast algorithm (`shadowcast.py`)
- Visible cells computed per entity
- Entity tracking of what they can see (`Senses.entities`)

### GridMap Spatial System
- Tile storage with walkable/visible flags
- Entity position registry
- Cell subscription for spatial events
- `SpatialChangeEvent` fired on movement

---

## Partially Implemented

### Movement Cost Calculation
**Current**: `cost = len(path)` - each tile = 1 movement
**Problem**: Assumes 1 tile = 5 feet, but no explicit conversion

**Gaps**:
- No difficult terrain support (should cost 2 per tile)
- No climbing/swimming cost (1 extra foot, 2 in difficult terrain)
- No crawling cost (1 extra foot while prone)
- No standing up cost (half movement to stand from prone)

### TileData Properties
**Current** (`gridmap.py:467-474`):
```python
class TileData:
    walkable: bool = True
    visible: bool = True  # blocks vision
    name: str = "Floor"
    sprite_name: Optional[str] = None
```

**Missing**:
- `difficult: bool` - doubles movement cost
- `movement_cost: int` - custom cost per tile (for water, etc.)
- `elevation: int` - for climbing/falling
- `light_level: Literal["bright", "dim", "dark"]` - for vision

---

## Not Implemented

### Special Movement Types
| Type | SRD Rule | Implementation |
|------|----------|----------------|
| **Difficult terrain** | 1 foot costs 2 feet | Tile flag + pathfinding cost multiplier |
| **Climbing** | 1 extra foot (2 in difficult) | Check tile, modify cost |
| **Swimming** | 1 extra foot (2 in difficult) | Check tile, modify cost |
| **Crawling** | 1 extra foot (while prone) | Check Prone condition, modify cost |
| **Standing up** | Costs half your movement | Action when prone |

### Jumping
| Type | SRD Rule | Notes |
|------|----------|-------|
| **Long jump** | STR score feet (with 10ft running start), half standing | Could be action or part of move |
| **High jump** | 3 + STR mod feet (with running start) | Vertical movement |

### Vision and Light
| Condition | SRD Effect | Current Support |
|-----------|------------|-----------------|
| **Lightly obscured** (dim light) | Disadvantage on Perception | Not tracked |
| **Heavily obscured** (darkness) | Effectively Blinded | Not tracked |
| **Bright light** | Normal vision | Not tracked |
| **Darkvision** | See in dark as dim light | Not tracked |
| **Blindsight** | Perceive without sight | Not tracked |
| **Truesight** | See through everything | Not tracked |

### Falling
- **Damage**: 1d6 bludgeoning per 10 feet, max 20d6
- **Effect**: Land prone unless avoid damage
- **Not implemented** - need elevation system

### Suffocation
- Hold breath: 1 + CON modifier minutes
- After: CON modifier rounds before dropping to 0 HP
- **Not implemented** - need breath tracking

### Resting

#### Short Rest (1 hour)
- Spend Hit Dice to heal (roll + CON mod)
- **Partially supported**: HitDice exist but no "spend" mechanic
- Need: `HitDice.spend(count)` method, healing application

#### Long Rest (8 hours)
- Regain ALL lost HP
- Regain half of total Hit Dice (minimum 1)
- Can only benefit once per 24 hours
- **Not implemented** - need rest action

---

## CRITICAL: Combat Loop Architecture

This is the core system we need to implement for turn-based tactical combat.

### SRD Combat Flow

```
COMBAT START
├── 1. Determine surprise (Stealth vs Passive Perception)
├── 2. Establish positions (already have gridmap)
├── 3. Roll initiative (DEX check for all combatants)
└── 4. Begin rounds

ROUND (6 seconds game time)
├── For each combatant in initiative order:
│   ├── START OF TURN
│   │   ├── Trigger "start of turn" effects (conditions, etc.)
│   │   ├── Death saving throw if at 0 HP
│   │   └── Reaction refreshes (was used since last turn start)
│   │
│   ├── TURN
│   │   ├── Movement (up to speed, can split around action)
│   │   ├── Action (Attack, Cast Spell, Dash, etc.)
│   │   ├── Bonus Action (if available)
│   │   └── Free Object Interaction (one per turn)
│   │
│   └── END OF TURN
│       └── Trigger "end of turn" effects
│
└── Round ends, next round begins
```

### What We Have

| Component | Status | Location |
|-----------|--------|----------|
| Entity positions | ✅ | `gridmap.py` |
| Movement action | ✅ | `actions.py:Move` |
| Attack action | ✅ | `actions.py:Attack` |
| Action economy | ✅ | `action_economy.py` |
| Cost consumption | ✅ | `ActionEconomy.consume()` |
| Cost reset | ✅ | `ActionEconomy.reset_all_costs()` |
| Reactions | ✅ | `reactions.py` (opportunity attacks) |
| Conditions | ✅ | `conditions.py` |
| Events | ✅ | `events.py` |

### What We Need

#### 1. Combat/Turn Manager
```python
class CombatManager:
    """Manages turn-based combat flow."""

    combatants: List[UUID]           # Entities in combat
    initiative_order: List[UUID]      # Sorted by initiative
    current_turn_index: int           # Who's turn is it
    round_number: int                 # Current round

    def start_combat(self, entities: List[Entity]) -> None:
        """Roll initiative, sort combatants, begin round 1."""

    def next_turn(self) -> UUID:
        """Advance to next combatant's turn."""

    def end_combat(self) -> None:
        """Clean up combat state."""
```

#### 2. Initiative System
- `Entity.roll_initiative()` - DEX check, store result
- `Entity.initiative: ModifiableValue` - for bonuses (Alert feat, etc.)
- Tie-breaking rules

#### 3. Turn Lifecycle Hooks
```python
class TurnEvent(Event):
    """Events for turn lifecycle."""
    phase: Literal["start", "end"]
    entity_uuid: UUID
    round_number: int

# Conditions can register handlers for these
# e.g., Frightened checks visibility at start of turn
```

#### 4. Resource Reset Logic
| Resource | When Resets |
|----------|-------------|
| Reactions | Start of YOUR turn |
| Actions | Start of YOUR turn |
| Bonus Actions | Start of YOUR turn |
| Movement | Start of YOUR turn |

Currently `reset_all_costs()` exists but needs to be called at turn start.

#### 5. Condition Duration Tracking
Many conditions last "until end of next turn" or "for 1 minute" (10 rounds):
- Need duration tracking on conditions
- Need turn/round counter to check expiration
- "Concentration" for spells (not implemented)

### Integration with GridMap

The gridmap already supports:
- Entity position tracking
- Spatial events (entity entered/left cell)
- Cell subscriptions (entities watching areas)

For tactical combat, we also need:
- **Threatened squares**: Track which squares are in reach of hostile creatures
- **Opportunity attack triggers**: Already have this via `reactions.py`
- **Difficult terrain**: Add flag to TileData
- **Cover calculation**: Line from attacker to target, check obstacles

### Proposed Architecture

```
CombatManager (new)
├── Owns combat state (initiative, turn order, round)
├── Fires TurnStartEvent / TurnEndEvent
├── Calls ActionEconomy.reset_all_costs() at turn start
│
EventQueue (existing)
├── Routes TurnStartEvent to condition handlers
├── Conditions check for expiration
│
Entity (existing)
├── New: initiative ModifiableValue
├── New: roll_initiative() method
│
ActionEconomy (existing)
├── reset_all_costs() called by CombatManager
│
GridMap (existing)
├── No changes needed for basic turn structure
├── Future: difficult terrain, cover calculation
```

---

## Implementation Priority

### Phase 1: Basic Turn Loop
1. Add `initiative` ModifiableValue to Entity
2. Create `CombatManager` class
3. Implement `start_combat()` with initiative rolls
4. Implement `next_turn()` with resource resets
5. Add `TurnStartEvent` / `TurnEndEvent`

### Phase 2: Condition Integration
1. Add duration tracking to BaseCondition
2. Register condition handlers for turn events
3. Implement "until end of next turn" expiration
4. Implement "concentration" for future spell support

### Phase 3: Terrain and Movement
1. Add `difficult` flag to TileData
2. Modify Dijkstra to account for terrain cost
3. Implement standing up from prone (half movement)
4. Add crawling cost when prone

### Phase 4: Vision and Light
1. Add `light_level` to TileData
2. Implement darkvision check
3. Apply disadvantage in dim light
4. Apply Blinded in darkness

---

## Code References

| Feature | Location | Notes |
|---------|----------|-------|
| Movement action | `actions.py:67` | `Move` class |
| Path cost | `actions.py:85` | `len(self.path)` - no terrain multiplier |
| Dijkstra | `dijkstra.py` | Returns paths with uniform cost |
| TileData | `gridmap.py:467` | Missing difficult/light flags |
| ActionEconomy | `action_economy.py` | Has `reset_all_costs()` |
| Senses | `sensory.py` | FOV, visible entities |
| HitDice | `health.py:27` | Exist but no "spend" mechanic |

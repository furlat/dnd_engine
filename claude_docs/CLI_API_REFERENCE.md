# CLI API Reference

Documentation of actual API responses from the D&D Engine server.

## Endpoints

### POST /simulation/start-human

Starts a new combat with human control.

**Response:**
```json
{
  "status": "waiting_for_human",
  "encounter_uuid": "uuid",
  "entity_uuid": "uuid",
  "entity_name": "Hero",
  "round": 1,
  "turn_index": 0
}
```

---

### GET /state

Returns full game state (grid, entities, encounter).

**Response:**
```json
{
  "grid": {
    "min_x": 0, "min_y": 0, "max_x": 14, "max_y": 14,
    "tiles": [{"x": 0, "y": 0, "walkable": true, "visible": true}, ...]
  },
  "entities": [
    {
      "uuid": "uuid",
      "name": "Hero",
      "position": [2, 7],
      "hp": 10,
      "max_hp": 10,
      "ac": 15,
      "conditions": [],
      "is_dead": false
    }
  ],
  "encounter": {
    "uuid": "uuid",
    "name": "Arena Combat",
    "state": "active",  // "active", "ended"
    "round_number": 1,
    "current_turn_index": 0,
    "current_entity_uuid": "uuid",
    "initiative_order": [
      {"uuid": "uuid", "name": "Hero", "initiative": 22, "is_dead": false}
    ]
  }
}
```

---

### GET /encounter/current-turn

Returns current turn information.

**Response:**
```json
{
  "encounter_active": true,
  "round_number": 1,
  "turn_index": 0,
  "current_entity_uuid": "uuid",
  "current_entity_name": "Hero",
  "is_human_turn": true,
  "waiting_for_input": true,
  "controller_type": "human",
  "actions_remaining": 1,
  "bonus_actions_remaining": 1,
  "reactions_remaining": 1,
  "movement_remaining": 30
}
```

---

### GET /entity/{uuid}/available-actions

Returns all available actions for an entity.

**Response:**
```json
{
  "entity_uuid": "uuid",
  "attacks": [
    {
      "action_id": "attack_main_hand",
      "name": "Attack (Scimitar)",
      "description": "1d6 Slashing",
      "cost_type": "actions",
      "cost_amount": 1,
      "can_afford": true,
      "requires_target": true,
      "valid_targets": ["target-uuid-1", "target-uuid-2"],
      "valid_positions": [],
      "category": "action",
      "weapon_slot": "MAIN_HAND"
    }
  ],
  "movement": [
    {
      "action_id": "move",
      "name": "Move",
      "description": "30ft remaining",
      "cost_type": "movement",
      "cost_amount": 0,
      "can_afford": true,
      "requires_target": false,
      "valid_targets": [],
      "valid_positions": [[2, 8], [3, 7], [2, 6], ...],
      "category": "movement",
      "weapon_slot": null
    }
  ],
  "other_actions": [
    {
      "action_id": "dash",
      "name": "Dash",
      "description": "Gain 30ft extra movement",
      "cost_type": "actions",
      "cost_amount": 1,
      "can_afford": true,
      "requires_target": false,
      "valid_targets": [],
      "valid_positions": [],
      "category": "action",
      "weapon_slot": null
    }
  ],
  "bonus_actions": [],
  "reactions": [],
  "free_actions": [
    {
      "action_id": "drop_prone",
      "name": "Drop Prone",
      "description": "Drop to the ground (free)",
      "cost_type": "movement",
      "cost_amount": 0,
      "can_afford": true,
      "requires_target": false,
      "valid_targets": [],
      "valid_positions": [],
      "category": "free",
      "weapon_slot": null
    }
  ],
  "can_attack": true,
  "can_move": true,
  "remaining_movement": 30,
  "blocking_conditions": []
}
```

---

### POST /action/move

Execute a move action.

**Request:**
```json
{
  "entity_uuid": "uuid",
  "position": [5, 7]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Applied movement for Hero moves",
  "event_type": "movement",
  "event_data": {
    "start": [2, 7],
    "end": [5, 7]
  },
  "entity_hp": 10,
  "target_hp": null,
  "deaths": [],
  "triggered_reactions": [
    {
      "type": "opportunity_attack",
      "attacker": "Skeleton",
      "target": "Hero",
      "weapon": "Shortsword",
      "d20": 17,
      "attack_bonus": 4,
      "attack_total": 21,
      "target_ac": 15,
      "outcome": "Hit",
      "damage_rolls": [{"dice": [5], "bonus": 2, "total": 7}],
      "total_damage": 7
    }
  ],
  "turn_continues": true,
  "encounter_ended": false
}
```

**Note**: `triggered_reactions` contains any opportunity attacks that occurred during the movement. If the moving entity used Disengage, no opportunity attacks trigger.

---

### POST /action/attack

Execute an attack action.

**Request:**
```json
{
  "entity_uuid": "uuid",
  "target_uuid": "target-uuid",
  "weapon_slot": "main_hand"  // or "off_hand"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Attack executed",
  "event_type": "attack",
  "event_data": {
    "attacker": "Hero",
    "target": "Skeleton",
    "weapon": "Scimitar",
    "d20": 14,                    // Raw d20 result
    "attack_bonus": 4,            // Total modifier
    "attack_total": 18,           // d20 + bonus
    "target_ac": 13,              // Target's AC
    "outcome": "Hit",             // "Hit", "Miss", "Crit", "Crit Miss"
    "damage_rolls": [
      {"dice": [4], "bonus": 2, "total": 6}
    ],
    "total_damage": 6,
    // Legacy fields (for backwards compat)
    "roll": 18,
    "damage": 6
  },
  "entity_hp": 10,
  "target_hp": 7,
  "deaths": [],
  "turn_continues": true,
  "encounter_ended": false
}
```

**IMPORTANT**: `outcome` values are CAPITALIZED: "Hit", "Miss", "Crit", "Crit Miss"

---

### POST /action/dash

Execute the Dash action.

**Request:**
```json
{"entity_uuid": "uuid"}
```

**Response:** Same structure as move, `event_type: "dash"`

---

### POST /action/dodge

Execute the Dodge action.

**Request:**
```json
{"entity_uuid": "uuid"}
```

**Response:** Same structure as move, `event_type: "dodge"`

---

### POST /action/disengage

Execute the Disengage action.

**Request:**
```json
{"entity_uuid": "uuid"}
```

**Response:** Same structure as move, `event_type: "disengage"`

---

### POST /action/end-turn

End the current turn and advance the encounter.

**Request:**
```json
{"entity_uuid": "uuid"}
```

**Response:**
```json
{
  "status": "waiting_for_human",  // or "encounter_ended", "ai_turn_complete"
  "entity_uuid": "uuid",          // next human entity (if any)
  "entity_name": "Hero",
  "round": 2,
  "turn_index": 0,
  "ai_actions": [                 // Actions taken by AI during their turn
    {
      "type": "turn_start",
      "entity": "Skeleton",
      "message": "Skeleton's turn"
    },
    {
      "type": "move",
      "entity": "Skeleton",
      "from": [12, 7],
      "to": [8, 7],
      "message": "Skeleton moves from (12, 7) to (8, 7)"
    },
    {
      "type": "attack",
      "is_opportunity_attack": false,  // true if triggered by movement
      "attacker": "Skeleton",
      "target": "Hero",
      "weapon": "Shortsword",
      "d20": 15,
      "attack_bonus": 4,
      "attack_total": 19,
      "target_ac": 15,
      "outcome": "Hit",
      "damage_rolls": [{"dice": [5], "bonus": 2, "total": 7}],
      "total_damage": 7,
      "message": "Skeleton attacks Hero with Shortsword: Hit for 7 damage!"
    }
  ]
}
```

---

## Notes

1. **Attack outcome case sensitivity**: The `outcome` field uses capitalized values ("Hit", "Miss", "Crit") - display code normalizes to lowercase with `.lower()`.

2. **AI actions included**: The `end-turn` response now includes `ai_actions` array with details of all AI moves and attacks.

3. **Movement validation**: The `valid_positions` array in `movement` actions contains all reachable positions.

4. **Attack targets**: The `valid_targets` array in `attacks` contains UUIDs of entities in range. Empty if no targets in range.

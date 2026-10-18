# Godot client: folding bodies and items in player schema 16

The changes from schema 15 only. Reference fold: `dnd/player/reduction.py` (`enter_body`, `enter_item`,
`apply_actor_change_fact`, `clear_unseen_positions`). Golden vectors: `sdk/protocol/fold-vectors/bodies/*.json`,
written by `devtools/fold_vectors_bodies.py`; fold them and compare each step's `expected`.

## 1. What is gone

| Schema 15 | Schema 16 |
| --- | --- |
| `PlayerLineage.observations`, `PlayerInitialization.observations` (`PlayerObservation`: a body patch, a contact, item patches) | `bodies` (`BodyRecord`, §2); a body record carries no contact (the sensory fact does) |
| `EquipmentFact` (`kind: "equipment"`: the whole loadout, inventory and AC) | `ActorChangeFact` (`kind: "actor_change"`, §3): layer, inventory and armor class rows |
| `ConditionChangeFact` (`kind: "condition"`: the whole membership with `resulting_*`) | `ActorChangeFact`: membership, duration and stat rows |
| `ItemEffectChangeFact` (`kind: "item_effect"`: a key without value) | `ActorChangeFact`: the held item's effects row; a floor object's effects are its world update's |
| `ActorChanges`, `ItemPatch` | `BodyState` + `ActorBirth`, `ItemRecord` |
| `ItemLook.item_effects` | `PlayerItem.effects` (the look is static) |
| `PlayerActor.conditions[]`: `ConditionFact` (with `event_uuid`, `resulting_*`, `consumed`) | `ConditionMember`: `condition_uuid`, `name`, `category`, `behavior_id`, `state` |
| The removal of the seat's own condition on a creature it no longer sees | nothing (leaving view sends nothing; the caster's own `Concentrating` ends on its own body) |

Every other fact (damage, heal, temporary HP, life, faction, spatial, attack stance, the controller's
`item_charge`) is unchanged and still folds its after-values into the body.

## 2. A body entering view: `BodyRecord`

`{occurrence, actor_uuid, birth?, body, loadout?, items?}`, folded in occurrence order before the nodes at or after its
occurrence (as observations were).

- `birth` (`name`, `character_body_id`, `creature_content_ref`, `appearance`, `structural_base_size?`,
  `manifestation?`): present only the first time the seat receives this body. A record without `birth` for a
  body the client does not hold is an error.
- `body` (`BodyState`): every changeable field, current. Replace them all: the visual loadout (below), `normal_hp`,
  `maximum_hp`, `temporary_hp`, `temporary_hp_grant` (absent: none), `life_state`, `armor_class`, `conditions`
  (absent: none), `controlled_items` (the controller's inventory; absent: not controlled), `occupancy_layer`
  (absent: none; sent to the controller or a visual contact), `resolved_size` (absent: none), `faction` (absent: none), `remains_disposition` (absent: intact), `spatial_disposition`
  (absent: present).
- Keep `last_visual_position` (contacts set it) and `present`. A body whose lifetime ended (`present` false)
  ignores every later record and row.
- `body.visual_loadout_id` names the body's visual loadout by content id. `loadout` carries its value
  (`active_weapon_set`, `layers`) the first time the seat receives that id; keep a table `{id: value}`, never
  pruned, and set the body's loadout to the value of its id. Later `layer` and `active_weapon_set` rows change the
  body's own value, not the table.
- `items`: the records of the items the body shows the seat (§4), except those that carry nothing new (look
  already sent, no state, no effects). Each item the body shows (its `controlled_items`, else its loadout's
  layers) that has no record here has no effects: clear them.

A body is sent whole whenever it enters the seat's composed view, also again after leaving it: the record
replaces what the client remembered.

## 3. A change to bodies the seat perceives: `ActorChangeFact`

`{kind: "actor_change", actors: [{actor_uuid, rows}], items?}`. Fold `items` first (§4), then each actor's rows
in order. Rows are tagged by `field`:

| `field` | Row fields | Fold |
| --- | --- | --- |
| `normal_hp`, `maximum_hp`, `temporary_hp`, `armor_class` | `value` | replace |
| `temporary_hp_grant` | `value` (null: none) | replace |
| `resolved_size` | `value` | replace |
| `spatial_disposition` | `value` | replace |
| `active_weapon_set` | `value` | replace `visual_loadout.active_weapon_set` |
| `condition` | `condition_uuid`, `member?`, `consumed?` | with `member`: set the membership of that uuid (in place if held, else appended); without: remove it (`consumed` tells how it ended); removing an absent one does nothing |
| `condition_duration` | `key`, `duration` | replace the held membership's `state.duration` (nothing if not held) |
| `layer` | `slot`, `layer?` | with `layer`: set that slot (in place if held, else appended); without: remove the slot |
| `inventory` | `item_uuid`, `held` | `held`: append the item to `controlled_items` if absent; else remove it |
| `item_effects` | `item_uuid`, `effects` | replace that item record's `effects` |
| `item_effect_duration` | `key`, `item_uuid`, `duration` | replace that effect's `duration` |
| `item_state` | `item_uuid`, `changes` | replace those fields of that item record's `state` |

The order matters: re-wearing an item in its own slot is a slot removal then a set, which moves the slot last.
Durations travel only to the controller; other seats receive memberships and effects without them.

Edge cases (as `apply_actor_change_fact` does them):
- an `actors` entry for a body the client does not hold is an error;
- an `inventory` row on a body without `controlled_items` is an error;
- an item row (`item_effects`, `item_effect_duration`, `item_state`) for an item record the client lacks, an effect
  it lacks or a record without `state` does nothing;
- a `condition_duration` row for a membership the body does not hold does nothing.

## 4. Items

The client's item record is `{look, profile?, state?, effects}`, never pruned (a destroyed item's record stays;
`item_charge` with `item_destroyed` no longer deletes it).

`ItemRecord` `{item_uuid, look?, profile?, state?, effects?}` (an item entering the seat's view):
- `look` (static): present the first time the seat receives this item; keep it.
- `profile` (static, the controller's): present the first time; keep it.
- `state` (the controller's): replace when present.
- `effects`: replace (absent: none).

## 5. A cell the seat sees shows what is there

After each sensory fact's senses fold: a living body (not dead, `present`, not controlled by the seat) whose
`last_visual_position` is a visible cell and which is not an entity contact of the composed view loses its
`last_visual_position`. Its other values stay remembered.

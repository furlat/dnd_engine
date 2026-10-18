# Godot client: folding the HUD in player schema 16

The changes from schema 15 only. Reference fold: `dnd/player/reduction.py` (`apply_hud`, `changed_sheet`,
`displayed_initiative`). `player_schema_version` is 16 with a new `schema_digest`
(`sdk/protocol/protocol-identity.json`); saved `PlayerSequence` packets are schema 9 (they no longer carry
HUDs: `huds` is gone and `initialization.hud` is absent).

## 1. `PlayerHUDPatch`

| Field | 15 | 16 |
| --- | --- | --- |
| `generation`, `observer_uuid`, `revision` | always present | removed (the update's envelope names the seat) |
| `sheet_order` | the sheet order when it changed | removed |
| `initiative` | the order when it changed | the order's perceived part when sent (see §3); absent when not sent |
| `sheets` | changed sheets | the same; absent when empty |

A sheet the client does not hold arrives whole (every field below except `resource_values`) and is
appended. At initialization the sheets arrive in their display order.

## 2. `SheetChanges` and the sheet

- **Removed from the sheet and its changes:** `name`, `portrait_key`, `normal_hp`, `maximum_hp`. Read them
  from the character's body: `actors[actor_uuid].name`, `.appearance.portrait_key`, `.normal_hp`,
  `.maximum_hp` (the body facts already kept them current).
- **New `resource_values`:** `[{key, current, maximum}]`. Each row replaces `current` and `maximum` of the
  held `resources` row with that `key` (its `label` is unchanged). A key the sheet does not hold is an error.
- `resources` is sent whole only when the sequence of keys changes (first sheet, a rank or resource gained
  or lost); otherwise changed rows come as `resource_values`.
- Every other field is unchanged and still replaces the held value when present.

## 3. Initiative

The client shows `initiative` filtered to what the seat perceives now: its controlled actors plus every
entity contact of every member's senses (`perception.members[*].entities`). Leaving perception sends
nothing; the client's filter hides it. The server resends `initiative` (the end order filtered by the
seat's perception) at initialization, when an order change shows under the current perception, or when
anything entered the seat's perception.

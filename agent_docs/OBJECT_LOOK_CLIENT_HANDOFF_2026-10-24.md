# Client handoff: an object's look can be sent again (player schema 20)

From the server branch `object_appearance_opus`, plan [OBJECT_APPEARANCE_PLAN_2026-10-24](plans/OBJECT_APPEARANCE_PLAN_2026-10-24.md).
No wire type changed. Only the meaning of `WorldUpdate.object_looks` and the schema number changed.

## What changes

- **Re-sent looks.** An `ObjectLook` row can now arrive again for an item uuid the client already holds. This happens whenever the object's look differs from the last one the seat was sent. Examples:
  - a display rack emptying (`swords_full`, `swords_partly_empty`, `swords_empty`);
  - a destroyed object's passage;
  - (next step on this branch) a camouflaged object a party finds, which turns from its camouflage look into its own look.
- **The client replaces the held look.** Schema 19 clients raise on this: the Python reference fold raised "An object's look changed", and Godot raises "A static content id names another value" (`sdk/fold_world.gd:16`).
- **The object's row comes in the same update** as its re-sent look. Fold the static rows first, as today, then the object row, which joins the new look.
- **All other static rows keep their constancy check:** tile looks, boundary structures and residue materials.

## Camouflage (built on this branch)

- **A seat whose party hasn't found a camouflaged object is sent it as what it shows.** For the secret door, that is the wall it is set in:
  - `item_id` `environment.wall.fantasy_a1`, its name and its glyph;
  - a WALL boundary structure with the door's own blocked channels;
  - no door mechanism or swing, no hit points, no open state, and no damage facts.
- **When the party finds it,** by notice, Search, or seeing it open, the seat gets a new look row (the door's) and the object's row with its door state. This is the same re-sent look as above. A seat whose party never found it keeps the wall.
- **An open or broken camouflaged object is shown as itself to every seat.**
- **Nothing new on the wire:** no new field and no new message.

## Reference

- Python reference fold: `dnd/player/world_reduction.py` `fold_static_rows` (the object-look loop now assigns).
- Server: `dnd/player/world_publication.py` `_look`, with the per-seat last look in `dnd/player/static_sent.py`.
- Seat test: `tests/player/test_hidden_objects_publication.py::test_a_rack_emptying_reaches_the_seat`.
- Regenerated generated files: `sdk/protocol/*.json`, `sdk/python/src/dnd_player/contracts.py`, `sdk/player-typescript/src/contracts.generated.ts`, and the identity files. No hand-written SDK or client code was changed.

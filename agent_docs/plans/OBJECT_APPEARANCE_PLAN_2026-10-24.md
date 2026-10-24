# Camouflage: the renderer data takes an alternative path by state

Status: plan, 24 October 2026, branch `hidden_knowledge_opus` at `5dd6e02784`. Rewritten after the human's
correction; not implemented.

## 1. The request

The human, 24 October: "the state of an object for visibility depends both from objective state like open
closed and by subjective uuid based like discovered or camouflaged / hidden [...] doing the extra check
exclusively when necessary." And: "it is a fucking change to the data we offer the renderer with
alternative path based on state do not make it more complicated than it needs to be."

The human's answers:
- Camouflage is built now.
- An open secret door is open, and you see through it.
- Hitting a camouflaged thing shows nothing, like hitting an invisible creature.

## 2. The rule

    renderer data for a seat = camouflage data   the object is camouflaged in its current objective state,
                                                 and no member of the seat's party knows it
                               its own data      otherwise (as today)

**Camouflaged in its current objective state** means intact and not open. An open or broken secret door is a door (or a hole) for everyone.

**Camouflage data is renderer data only:**
- look (item_id, visual variant);
- name;
- map character;
- boundary structure (the wall's).

A seat that gets it gets nothing else about the object: no door fields, hit points, open state, effects or contents, and no damage facts. There is no second object.

**Hidden presence stays as built.** It is perception (the engine doesn't perceive the object at all). Camouflage is not perception: everyone perceives a wall there. So it lives in the renderer data, the one place it changes anything.

## 3. Changes

1. **The look may change, so it travels by id in the state.**
   - `ObjectState.look` holds a content id: a digest of the look row without its uuid.
     - The digest is a pure function next to `structure_id` (`world_columns.py:98`). The client codec imports that module, so it holds no memo.
     - The memo is a dict on `SessionProjection`, like `loadout_ids` (`projection.py:1876`), passed in.
   - Look rows are sent once per id, as boundary structures are (`world_publication.py:196-210`).
   - This also delivers the two objective changes that never reach a seat today:
     - a rack emptying (`environment_interactables.py:583-588`);
     - a destroyed object's `contact_passage` (`base_item.py:501-507`).
   - The known-attachments use of the uuid set (`projection.py:1286, 1562`; `content_composition.py:100`) keeps its own uuid set.
   - Schema 20. A client handoff document (the client reads `looks[state.look]`). No client or `sdk/` file is touched.
2. **Data.**
   - `ConcealedAspect.CAMOUFLAGE` joins `NOTICED_ON_OBJECTS`, so passive Perception, Search and party knowledge work as for the other aspects.
   - It also joins `Search.searched_aspects` (`actions.py:3108`) and the plain-view write on opening (`environment.py:466`). Whoever sees the door open learns it.
   - The record carries `shows: Camouflage`, a frozen leaf model of the four renderer fields above, in `concealment_types.py`.
   - The item's presentation state carries a server-only `camouflage` field, never on the wire, derived at snapshot like `presence_concealed`. It holds the holder's uuid and the record's `shows`, or None when the object is open or not intact.
3. **Knowledge reaches the seat on the event that already carries it.**
   - Learning is a general feature, and it always has a source event. The fact is `SensoryUpdateEvent.concealed_noticed`, the holders an observer noticed. It already covers:
     - passive Perception;
     - plain view, so whoever sees the door open learns it;
     - exposure.
   - It is rooted in its cause and already recorded (`event_record.py:113`).
   - Search's finds join the searcher's own sensory update, which Search already publishes (`actions.py:3164`, `entity.py:5370`): one argument.
   - The session projection folds these facts once per event, for all seats, into the knower keys per holder (the noticer's faction, or its uuid when it has none). A party member in another seat therefore knows too.
   - There is no republish of the object and no physical change. `refresh_object_state` re-places the object and bumps its optical and movement revisions, so it is not used.
4. **Seat, in one place.**
   - `disclosed_floor_item` (`world_publication.py:112`) gives the camouflage row when `camouflage` is set and the seat's knower keys don't meet the folded keys of its holder.
   - The objects whose holders a fact names count as written for this walk, so their rows are rebuilt.
     - The camouflage row is the four fields and the placement; every other field takes its default.
     - The seat's knower keys are its members' factions and uuids (`SessionProjection.actors[...].faction`). They are computed once per walk in `projection.py` and passed as a value: `world_publication` cannot import `SessionProjection`.
   - The look row comes from that disclosed row, not the undisclosed item (`:331`).
   - For a camouflaged object, the damage fact (`projection.py:1545`) and contents (`contents_granted`) are skipped.
5. **AI.** `AIKnowledge` folds the same `concealed_noticed` facts from its observers' updates, and `world_projection.project_object` and `project_tile` (`:58-122`) apply the same test with its knower keys.
6. **Content.** `build_secret_door` installs CAMOUFLAGE showing `environment.wall.fantasy_a1` instead of PRESENCE.

## 4. Cost

- **Ordinary objects:** one `camouflage is None` test per emitted row, and one memoized look-id lookup.
- **Camouflaged objects:** one set intersection per emitted row.
- **Knowledge changes:** one fold per notice, on an event that is already published. No new event and no republish.
- **Nothing per settlement:** the notice scan already covers concealed hosts.

## 5. Steps

0. **A seat-level test** showing today's rack bug, plus how seat logs name an object. Baseline `devtools/performance/gallery_crowd.py` (`publication_ms`) on `5dd6e02784`.
1. **The look by id** (change 1), with the rack test and the client handoff.
2. **Camouflage** (changes 2-6). Tests at the seat boundary (`tests/player/test_hidden_objects_publication.py`) and the engine boundary (`tests/engine/test_party_knowledge.py`):
   - goblins see a wall and get no door fields or damage;
   - heroes who searched see the door;
   - an opened door is a door for everyone.
3. **Timing**, base against new interleaved under load, and the six suites.

Anti-slop and anti-OOP reviewers read the plan and each step's diff, and a plan-adherence tracker runs during implementation.

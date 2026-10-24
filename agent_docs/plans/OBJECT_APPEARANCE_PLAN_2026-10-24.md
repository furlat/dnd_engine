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

1. **The look may change, so a seat is sent it again when it differs.**
   - The seat remembers the last look sent per object: `StaticSent.object_looks` becomes a uuid-to-look dict (`static_sent.py:23`).
     - `_look` (`world_publication.py:196-199`) sends a look row when it differs from that last one.
     - The look and the row always travel together, because a changed look comes with a changed row.
   - The reference fold replaces the look instead of raising "An object's look changed" (`world_reduction.py:51-53`). The Godot client does the same, as stated in the client handoff.
   - The wire types don't change, so the generated SDK contract is unchanged.
     - The schema number becomes 20, because clients must now accept a second look.
     - `devtools/export_player_protocol.py` regenerates only the identity files, as the schema-19 commit `5c4f28c063` did.
     - No hand-written SDK or client code is touched.
     - (Not a look id in the state: that would also regenerate the contract and the cross-client golden vectors in `sdk/protocol/fold-vectors/world/`, for the same result.)
   - The uuid uses keep working: dict union and membership (`world_publication.py:320, 332`; `projection.py:1286, 1562`).
   - This also delivers the two objective look changes that never reach a seat today:
     - a rack emptying (`environment_interactables.py:583-588`);
     - a destroyed object's `contact_passage` (`base_item.py:501-507`).
2. **Data.**
   - `ConcealedAspect.CAMOUFLAGE` joins `NOTICED_ON_OBJECTS`, so passive Perception, Search and party knowledge work as for the other aspects.
   - It also joins `Search.searched_aspects` (`actions.py:3108`) and the plain-view write on opening (`environment.py:466`). Whoever sees the door open learns it.
   - The record carries `shows: Camouflage`, a frozen leaf model of the four renderer fields above, in `concealment_types.py`.
   - The item's presentation state carries a server-only `camouflage` field, never on the wire, derived at snapshot like `presence_concealed`. It holds the holder's uuid and the record's `shows`, or None when the object is open or not intact.
3. **Knowledge reaches the seat on the event that already carries it** (CAMOUFLAGE records are party-scoped, so a key is the noticer's faction, or its uuid when it has none, as `knower_key` gives).
   - Learning is a general feature, and it always has a source event. The fact is `SensoryUpdateEvent.concealed_noticed`, the holders an observer noticed. It already covers:
     - passive Perception;
     - plain view, so whoever sees the door open learns it;
     - exposure.
   - It is rooted in its cause and already recorded (`event_record.py:113`).
   - Search's finds join the searcher's own sensory update, which Search already publishes (`actions.py:3164`, `entity.py:5370`): one argument.
   - The session projection folds these facts once per event, for all seats, into the knower keys per holder. A party member in another seat therefore knows too.
   - There is no republish of the object and no physical change. `refresh_object_state` re-places the object and bumps its optical and movement revisions, so it is not used.
4. **Seat, in one place.**
   - `disclosed_floor_item` (`world_publication.py:112`) gives the camouflage row when `camouflage` is set and the seat's knower keys don't meet the folded keys of its holder.
     - The camouflage row is the four fields and the placement; every other field takes its default.
   - A notice in the walk whose knower key is one of this seat's keys makes that object count as written for this seat only. Its row is rebuilt for the seats that learned it and for no others, so the others get no tell.
     - The seat's knower keys are its members' factions and uuids (`SessionProjection.actors[...].faction`). They are computed once per walk in `projection.py` and passed as a value: `world_publication` cannot import `SessionProjection`.
   - The look row comes from that disclosed row, not the undisclosed item (`:331`).
   - For a camouflaged object, the damage fact (`projection.py:1545`) is skipped. Contents need no change: `contents_granted` already requires the object open or broken (`:107-109`).
   - Seat logs need no change. An object is never identified (`encounter.py:157-161`), so its name is hidden from every seat's log (`subjective_combat_log.py:207-210`).
   - Object action rows: CAMOUFLAGE joins `hides_actions_from` through `NOTICED_ON_OBJECTS`, so a creature that doesn't know the door gets no row on it at all, and no name with one. The one tell is that this "wall" offers no Attack.
5. **AI.**
   - `AIKnowledge` folds the same `concealed_noticed` facts from its observers' updates.
   - `world_projection.project_object` and `project_tile` (`:58-122`) apply the same test with its knower keys.
   - A camouflaged object's fact is the four fields and its blocking only: no `is_usable` and no `is_open`.
   - (A same-faction member under another controller is not folded. The engine's action gate still decides what the AI may do.)
6. **Content.** `build_secret_door` installs CAMOUFLAGE showing `environment.wall.fantasy_a1` instead of PRESENCE.

## 4. Cost

- **Ordinary objects:** one `camouflage is None` test per emitted row, and one look comparison where today there is a set lookup.
- **Camouflaged objects:** one set intersection per emitted row.
- **Knowledge changes:** one fold per notice, on an event that is already published. No new event and no republish.
- **Nothing per settlement:** the notice scan already covers concealed hosts.

## 5. Steps

0. **Baseline:** `devtools/performance/gallery_crowd.py` (`publication_ms`) on `5dd6e02784`.
1. **The look sent again** (change 1). A seat test: the rack's emptying reaches the seat. The client handoff.
2. **Camouflage** (changes 2-6). Tests at the seat boundary (`tests/player/test_hidden_objects_publication.py`) and the engine boundary (`tests/engine/test_party_knowledge.py`):
   - goblins see a wall and get no door fields or damage;
   - heroes who searched see the door;
   - an opened door is a door for everyone.
3. **Timing**, base against new interleaved under load, and the six suites.

Anti-slop and anti-OOP reviewers read the plan and each step's diff, and a plan-adherence tracker runs during implementation.

## 6. Review record (24 October)

- **Rejected:** giving the camouflage a real wall's hit points and face residues. The human: "do not show the fuck nothing".
- **Accepted:**
  - rebuild a row only for the seats that learned;
  - the AI's camouflage fact;
  - the uuid uses and the reducers named;
  - the record scope.
- **Removed as unneeded:** the log probe (objects are never identified) and skipping contents (already gated).
- **From the anti-OOP review:** the knower keys are passed in as a value. The digest memo is gone, because option B has no digest.

## 7. As built (24 October)

**Steps 1 and 2 are built.**
- Step 1: `b2e3bf4936`.
- Step 2: `7212003911`, and step 2b in the commit after it.

**Deviations from §3:**
- **Notices travel seat-independently.** A foreign seat's sensory body is a header (`capture.py:442`), so the notices are read once from the native events, the way `native_logs` are:
  - on `CompletedLineage.notices`;
  - on `WorldInterval.notices`, for the startup walk, so every seat starts knowing what its party found before it, a partner's notice in another seat included.
- **The fold keeps every notice, but a seat's found set reads only the camouflage index** (`WorldFacts.camouflaged_by_holder`). Filtering at fold time lost the notice of a door placed in view, because its sensory child folds before the placement. Trap knowledge reaches seats as spatial effects. With no camouflage, a seat's per-event check is one emptiness test.
- **The knower key is the noticer's faction, or its uuid without one.** That is right because a CAMOUFLAGE record is party-scoped. The record's validator now enforces it, together with "camouflage, and only it, shows a look".
- **`found` is a required argument** of every per-seat function and of the AI's `project_object`. A caller that forgets it fails instead of silently showing the wall. The oracle (`seat_oracle.py`) reads it from the live records with `knows`. The authoring export passes an empty set.
- **The one rule `camouflaged()` lives in `dnd/core/item_types.py`,** beside the state it reads, so the seat and the AI share it (`dnd/ai` cannot import `dnd/player`).
- **The camouflage row and the AI fact carry the object's physics:**
  - blocking, passage and pickability;
  - the residues on observed faces, because what is on a surface is seen. This is not the rejected imitation of a wall's own residues.
  - The AI fact has a wall's shape: `is_usable` false, no `is_open`, no charges.
- **`project_tile` is unchanged.** It reads only the boundary's blocked channels and passage, and the camouflage's wall structure is built from the door's own channels.
- **An opened door puts every presence or camouflage record in plain view** (`SEEN_WHEN_OPEN`), not just the first.

**Step 3, timing** (24 October, interleaved under load; the scripts are in the session scratchpad and not committed):

| Measure | Result |
| --- | --- |
| Engine (`hidden_knowledge_timing.py`, base `5dd6e02784` against `6c3125cebf`, load 25) | Equal or faster on every row: refreshes, moves, firing, search, the packed room |
| Camouflage, seat publication of 6 moves, 1 seat, 20 and 60 doors (camouflaged against plain) | 17.7 against 18.1 ms; 15.7 against 15.0 ms |
| Same, 4 seats | 27.9 against 26.1 ms; 30.5 against 25.7 ms |

With 4 seats and 60 camouflaged doors in view, that is about +0.8 ms per move: a few microseconds per seat per camouflaged object. Ordinary objects pay nothing measurable.

**Final commit `a557052648`:**

| Measure | Result |
| --- | --- |
| Publication (`gallery_crowd.py`, base `5dd6e02784` against new, 5 rounds, load about 40), median publication ms | caster steps: equal or faster (character seats 52 / 51 / 51 against 57 / 55 / 60); Ice Storm: equal (faction 39 against 40.5; character 192 against 188); Fireball, faction seats: equal (74.3 against 76.6) |
| Fireball, one seat per member | first run: 449.9 against 400.9 ms, re-run alone because it looked anomalous; 9 interleaved rounds, alternating order: new 341.6 (min 316.7) against base 355.3 (min 320.1) ms. Not slower; the first difference was load noise (load 47) |
| Camouflage against plain doors (final), 6 moves | 1 seat: equal at 20 doors, 19.7 against 14.1 ms at 60; 4 seats: 26.4 against 22.9 ms at 20 doors, 28.1 against 22.9 ms at 60 (about +0.9 ms per move) |

**Kept as decided, against review:** the camouflage shows no hit points. The human: "do not show the fuck nothing".

**Known limit:** an AI folds only its own observers' notices. A same-faction creature under another controller is not folded, and the engine's action gate still decides what the AI may do.

**Reveal on hit** (the human, 24 October: "make that attacking it reveals it like in dark soul"):
- Damage taken by a camouflaged object removes its camouflage, for everyone, from any attack or area (`BaseItem.receive_damage`). This is the same physical end as hidden contents found by Search Inside.
- The condition's removal republishes the object, so every seat and the AI see the door. No knowledge fold is involved.
- The "no damage shown" gate and its captured-contact set are gone. The camouflaged object can no longer be damaged and stay hidden, so that tell is gone too.
- Walls in reach are listed as Attack targets, as before, and so is the camouflaged door. An attacker that hasn't found it sees its target named as the wall (`BaseItem.name_seen_by`, the one `camouflaged()` rule): it was "Secret stone door" before.

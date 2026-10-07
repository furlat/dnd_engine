# October 6 live playtest — complaint and repair ledger

October 7 additions remain in the same recovery scope: full GPU migration is
specified in the [reviewed addendum](../GPU_RENDERER_AND_MEDIA_READINESS_2026-10-07.md).
P05/P06/P27 include repairing oversized/wasteful VFX packing before memory
budget selection. The human explicitly keeps 32 FPS; source frame reduction is
not the fix. P08 additionally includes spells that seem too fast: trace effective
cast/travel/impact/retirement timing separately from source FPS. Initial measured
packing opportunities and timing candidates are in the
[audit](GPU_PACKING_AND_TIMING_2026-10-07.md); none are marked complete by a plan.

**Current status: implementation resumed by the human.**
The [recovery plan](../PLAYER_PLAYTEST_RECOVERY_PLAN_2026-10-06.md) owns the
implementation sequence and acceptance for P01–P30. Native mechanics latency
and rendering latency are measured independently. This ledger preserves complaints;
the implementation receipt distinguishes completed checks from outstanding work.

Later human clarification: P05/P27 must investigate accumulated **engine** and
startup regressions, not assume the delays are only rendering or WSL. Section 2
of the recovery plan now requires native-only operation profiles, actual-launch
startup breakdown, existing timing hooks and comparable historical evidence
before accepting scheduling/renderer repairs as sufficient.

This is the continuing work list. New complaints append to it; they do not
replace outstanding work. A passing example is not evidence for every case.
Earlier UI composition requirements and repairs remain recorded in
[the UI repair report](PLAYER_UI_REPAIR_2026-10-06.md).

| ID | Human complaint / required result | Current evidence and next verification | Status |
| --- | --- | --- | --- |
| P01 | Opening two doors must permit movement through them; a clicked destination sometimes sends the actor to a corner and stops. | Initial crypt discovery refreshes after each door opening; movement revisions and path caches invalidate. Reproduce with party members in the passage and inspect native termination reason. | Investigating |
| P02 | The displayed path arrow must be the actual executed route. | Both UI preview and native adapter select the discovered safe/ordinary path. Verify their full path against committed movement steps with doorway occupancy. | Verification pending |
| P03 | Walk through allies, ending on a free cell. Other characters currently obstruct passage. | Existing traversal permission only admits Halfling Nimbleness. Endpoint occupancy already has a separate rule. Add ally passage there and verify occupied endpoints remain rejected. | Reproducing / fixing |
| P04 | Walls covering visible tiles must be transparent automatically (human clarified; no Alt requirement). | Apply the same foreground cutaway to drawing and picking. Native visibility still determines which tiles/entities are revealed; preserve door interaction and Ctrl attack. | Implementing |
| P05 | Startup takes too long; WSL/C: may contribute. | Measure imports, session creation, media loading and first frame separately. Do not guess or move the repository. | Measuring |
| P06 | Low FPS, camera changes and especially WASD panning lag badly. | Measure warmed live drawing at the actual supported monitor resolution, including picking and camera movement. Compare cold/warm and camera return costs. | Measuring |
| P07 | Visible enemies appear without portraits. | Supplied screenshots show enemy initiative frames with HP bars but no images. Resolve exact creature presentation against delivered portrait assets; no invented artwork. | Investigating |
| P08 | Fireball and Scorching Ray projectiles are incorrectly oriented. Both directional sprite choice and trajectory alignment are required. | October 7 reconfirmation: audit the shared projectile path at every camera, non-cardinal angle and elevation; verify actual pixels. Profile Fireball native work, media preparation and drawing separately. | Investigating; not closed by an authored flag change |
| P09 | Scorching Ray hand colour differs from its spell. | Compare source projectile palette with authored hand material; audit the shared palette derivation for the same defect. Preserve palette replacement, never tint multiplication. | Investigating |
| P10 | Spell targeting has no usable AoE or impact preview. | Trace native selection-preview geometry through hover targeting and actual rendering. Include circle/cone/line/ordered wall and ordinary impact targeting where admitted. | Investigating |
| P11 | Add a visible FPS counter so frame drops can be observed during real play. | Small readable counter, with frame time; no diagnostic text flood. | Implementing |
| P12 | Curate a native Windows uv environment, so the game runs without WSL and platform costs can be compared. | Separate environment and launcher using the same checkout, locked dependencies and existing assets. Preserve Linux environment. | Implementing |
| P13 | Door opening works from an extra tile away; the adjacency rule belonged to old full-tile doors. | Wall-edge doors should be operated from either incident support cell, without the extra neighbouring-cell ring. Keep discovery, automatic approach and execution aligned. | Investigating |
| P14 | Fireball still has ugly clipped chunks when its area includes unseen cells; show the visible explosion intact. | Recover screenshot and inspect the shared area-media visibility cut. Do not reveal hidden entities/tiles to repair effect geometry. Check related area effects for the same regression. | Investigating |

- **P08 extension, October 7:** this is a shared projectile requirement across all
  spells: choose the proper directional art, align it to the projected trajectory,
  and check animation playback/travel speed. Fireball and Scorching Ray are examples.
  Avoid blanket speed changes that hide computation stalls or break contact timing.
- **P31 — a character at 0 HP still receives a turn:** distinguish native death-save
  processing from an actionable human turn. Verify dying/stable/dead action admission,
  automatic turn progression, and historical HUD state before choosing the repair.

## Prior environment complaints retained

- **P26 — one player, shared party view (critical):** combine current visibility
  and explored terrain of both controlled characters. Changing turns must not
  hide a battle witnessed by the other party member, omit enemy animations, lose
  portraits, or swap between incompatible maps. Shared knowledge must also feed
  navigation/target affordances; native actor range, physical obstruction and
  spell-specific line-of-sight requirements remain authoritative. Consume each
  causal event once even when both party observers witness it.
- **P27 — blocking live loop / repeated loading stalls (critical):** measure
  native execution, discovery, event capture, media preparation and drawing
  separately. Window input/drawing must remain responsive during engine work;
  preserve causal event order and never run concurrent mutations of the engine.
- **P28 — input ergonomics / accidental action spending:** audit click routing,
  confirmation and immediate self-actions against actual enabled affordances.
  UI clicks must never fall through into world actions or stale targets.
- **P29 — grid ignores geometry:** ground grid must use actual support elevation
  and scene occlusion, rather than being painted over walls, actors and props.

- **P21 — known enemy becomes “unknown” after an opportunity-attack death:**
  retain event-time identity through the end of its turn. A creature disappearing
  from current perception must not erase identity already established during
  that turn. Check the native projected log, including unseen-creature privacy.
- **P22 — camera-dependent doors/interactables:** south-facing wall doors are
  neither mouse-pickable nor highlighted by Alt until camera rotation. Check
  object registration, post-cut picking and Alt highlighting at all four camera
  angles. View rotation must not change the known set of interactable objects.
- **P23 — visible door with missing threshold/floor:** verify the room-side
  support beneath the door, its alignment and visibility cut. Do not reveal the
  unseen room beyond a closed door to make its threshold readable.
- **P24 — stuck interaction error:** “No admitted safe approach” remains forever.
  Use readable wording, expire transient errors, and clear them on new input.
- **P25 — suspicious low attack rolls:** verify the live launcher has no fixed
  dice/test seed and that attack dice are d20s. Compare recorded dice, advantage/
  disadvantage and modifiers with the displayed log; do not infer a defect from
  a short low-roll sequence alone.

- **P19 — Action Surge and unavailable actions:** depleted/unavailable actions
  must never enter the targeting/confirmation state. Self actions take one click.
  Remove redundant confirmation-symbol tooltips. Check common action dispatch.
- **P20 — duplicate Dash / Haste Dash:** keep one normal verb in the action bar
  while preserving the native restricted resource choice and attack economy.

- **P18 — movement into explored, out-of-sight ground:** native movement already
  admits retained explored paths; ground picking incorrectly required current
  visibility. Make explored ground clickable and show its native route, keeping
  hidden actors/objects undisclosed and execution collision checks authoritative.

- **P15 — zoom blocked:** launch starts at the previous maximum (100%). Allow
  inward zoom and verify cursor anchoring, while keeping wheel capture over UI.
- **P16 — ranged skeleton attack uses the wrong motion:** trace the actual
  selected weapon/attack event and modular recipe; preserve this regression
  check even when changing the encounter's enemies.
- **P17 — use completed creature artwork in the encounter:** replace the crypt's
  skeleton encounter roster with authored goblins; preserve exploration, traps
  and loot.
- **P12 Windows detail:** Code Integrity event 3077 blocked Pygame's
  `time.cp313-win_amd64.pyd` on first import. Subsequent profile completed. Do not
  disable Application Control. Verify repeat native imports and a launcher
  environment accessible outside the desktop application's redirected AppData.

- Wall/door illumination mismatch: shared observed illumination correction is
  implemented and covered by the preceding report's source/pixel checks.
- Desk clipping into the wall: moved in the crypt; broader asset alignment is
  documented in the human-delivered wall/floor handoff, not silently considered
  universally solved.
- Static walls: seven registered solid wall families currently have no selected
  destruction animation. This remains an asset/registration gap in that handoff;
  door/window animation coverage is not proof that all walls are animated.
- The actual playable launch remains the fixed Fighter/Sorcerer Lantern Crypt,
  not a demonstration gallery. Restart a running process to load source fixes.

## Evidence

- `.runtime/ui-repair-20261006/path-check/probe.py` and `probe.json`:
  initial door revision/disclosed-path check (not yet the occupied-door case).
- `.runtime/ui-repair-20261006/path-check/profile_play.py`:
  bounded 35-frame SDL-dummy profile at 2560×1440 with synthetic camera changes.
  It does not establish real WASD/display/command or long-session performance.
- Regression boundaries: native discovery/command/committed position; exact
  delivered UI media; projected projectile geometry and actual captured pixels.

No new gameplay rules, unrelated systems, generated art or other-chat messaging
are authorized by this repair list.

## October 7: additional live crash (P30)

Drinking a Haste potion can crash in `scene_actors` because a controlled companion
has no retained visual contact. Reproduced with the real Fighter/Sorcerer builds,
Haste-potion consumption and loss of the other hero's sight: an inventory update
republishes the projector's older actor snapshot, erasing the pose already
recorded by the sensory reducer. This is a general projection-memory defect,
not a Haste rule. Same-room contact masks it; separated heroes expose it.

Repair reuses the existing player sensory/spatial reducer inside projection so
gear observations retain the current disclosed pose. Binding failures now name
the actor, observer, cursor, contact and recorded member position. They still
raise; no skipped actors or blanket exception recovery. The affected regression batch passes 37 checks, including both walk/jump portal
arrival followed by a real inventory change. The actual crypt SDL loop also
completes both heroes drinking their Haste potions with retained positions and
matching latest/history. Evidence is in `potion-projection-tests.log` and
`potion-live-fixed.log` under the private recovery output.

Only explicitly inadmissible user commands now use `CommandRejected`; the live
loop catches this type only before native mutation. Unexpected `ValueError`s
and rendering/projection failures propagate. The separate command-boundary batch
passes 11 checks; this does not establish overall app completion or performance.

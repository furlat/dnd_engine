# Animation clip extraction and review

From the repository root, use the [WSL uv setup](../../README.md) and installed
`ffmpeg`/`ffprobe`. Export the same `UV_PROJECT_ENVIRONMENT` in each new shell:

```bash
export UV_PROJECT_ENVIRONMENT="$HOME/.cache/dnd-engine/venv"
uv run --no-sync python -m devtools.animation_review.capture
uv run --no-sync python -m devtools.animation_review
uv run --no-sync python -m devtools.animation_review.serve
```

Open <http://127.0.0.1:8767/>. `devtools.animation_review.capture` generates and saves the selected
native histories once; the next command renders those same saved inputs again.
The final command serves the local files, including the HTTP byte ranges
needed for browser video seeking. No game server or Node runtime is involved.
Capture uses SDL's dummy video driver by default and does not need
the desktop. MP4 is used for pause, seeking, frame stepping and efficient
parallel playback.

Only the capture command imports and executes native scenarios. It replaces selected inputs under
`.runtime/animation-review/inputs/<case-id>/input.json`. Both the first render
and later renders decode the saved sequence before reducing or binding it;
the renderer never receives the native producer's Python objects. With the replay command, missing input is an explicit error rather than a request to rerun
mechanics. Use the capture command again when intentionally changing a scenario or its
native mechanics. Each run copies its input alongside the video so replacing
the shared input does not alter older evidence.

New captures run each experiment once and record every explicitly named native
participant before its runtime closes. Each perspective has the same experiment
and native generation, its actual observer UUID and initialization cursor, and an
independent subjective sequence. `perspectives.json` lists its ordinary saved
input files. The original observer keeps the case ID; companion cards append
`--<role>`. Experiments with one actual participant have one perspective.

`input.json` now contains the public `PlayerSequence` packet. Its causal nodes
retain original identities and ancestry, with optional authorized facts; it does
not include objective diagnostic rows, foreign sensory payloads or other actors'
private inventory. The player reducer builds initial state from the packet's
recorded initialization. Both first capture and repeat playback decode these
saved public bytes before rendering. The private native version-2 archive is
saved separately as `native.json` for local debugging. Existing historical
native inputs remain unchanged; replay projects them into a run-local public
packet without rerunning mechanics. Run metadata records the Git branch, commit
and dirty status; replay does not walk or hash the source/assets. Review metadata
remains local development data rather than part of the player protocol.

Complete retained lineages are reduced and sampled through the same
`game/playback_frame.py` function used by the game.
Each recorded instant is drawn from all four camera quadrants in one pass,
then encoded as a synchronized 2×2 video: 0/1 above, 2/3 below. Defaults are
24 fps and 960×640 per corner, giving a 1920×1280 clip. Use the video's native
fullscreen control to inspect the pixels. The state/condition rules stay in
the engine; this recorder adds no animation rules or gameplay queue.

The original 72 experiments cover: melee profiles and outcomes, modular and
fixed-rig ranged attacks, ordinary movement, walking/jumping opportunity attacks
with save/miss/paralysis/death, paused retained playback, two-cast histories,
repeated targets, height and equipment roots, plus six continuing condition
histories: walking/jumping recovery, failed save, delayed recovery, Dodge expiry
and paused history while latest has recovered. Two healing cases use the
original standalone feedback context: capped living healing and a dying player
restored by native healing. Eight life-transition cases add real death-save
outcomes, stabilization/healing, death/revival, paused death while latest is
revived, and opportunity downing. Original badges accompany mechanical
DYING/STABLE, whose body remains Idle. Actual death plays Die and holds its
last frame until native revival restores Idle; the source has no stand-up clip.
The paralysis rider is the
existing configurable native mechanic, not a weapon-triggered Hold Person
spell. The pause case freezes an offline presentation clock over already
reduced history; live independent controller progression remains covered by
the encounter integration tests.

Fifteen visibility experiments add thirty subjective clips. They cover range
entry/exit/re-entry, crossing an actual open doorway in either direction,
observer motion, a closed-door control, stopping at the first visible point,
leaving the last point, equipment/HP changes while hidden and later
reacquisition, and paused historical playback. A real Dash enables one long
Move across two apertures, producing two separated visible runs inside the same
complete movement lineage. Native sensory facts and endpoint authority select
what each observer receives. A perspective with no perceived changes renders
its actual idle state for the normal lead/tail duration, without a synthetic
event.

The open-field fixtures use a 26×7 native map and cross the existing observer
radius: contact appears at 20 tiles and is absent at 22. They do not override
perception to manufacture an edge. The native acceptance matrix checks every
visibility row's initial contact, acquisition/loss order, moving participant,
and the two-aperture case's single movement root before clip review.

Fourteen concealment experiments add twenty-eight subjective clips. The
**subject** is the Invisibility caster or hidden actor; the **perceiver** is
the other actor, who may cast True Seeing or drink its potion. Each card labels
allied/opposing factions and its actual sight grant. Each viewpoint still has
four camera corners. The finite matrix is:

| Native experiment | Variants | Measured outcome for the perceiver |
| --- | --- | --- |
| Invisibility, move, reveal | Opponent attacks; ally drops concentration | Contact disappears and returns on the revealing action. |
| True Seeing spell, Invisibility, move, reveal | Allied and opposing | Contact persists; the subject is still mechanically Invisible. |
| Invisibility, True Seeing, native expiry | Opposing; paused history | Contact disappears, returns on the actual grant, disappears when its ten-round effect ends. |
| True Seeing and invisible doorway crossing | Opposing | The wall still conceals movement outside the aperture. |
| Bright-light Hide | Allied and opposing | Enemy observation withholds Hide from action discovery; allied observation allows its actual Stealth roll. |
| Dim-light Hide, move, ranged reveal | High and low Stealth | High conceals; low applies Hidden while contact persists. |
| True Seeing, Invisible + high Hidden, attack | Opposing | Truesight bypasses Invisibility but the native Stealth DC still conceals; attack removes both. |
| True Seeing, low Hidden, casting reveal | Opposing | Contact persists; Fire Bolt removes Hidden through the native handler. |
| True Seeing potion, Invisibility, move, reveal | Allied and opposing | Actual bonus-action use grants sight and consumes the owner's one-charge item. |

These histories use discovered actions and ordinary encounter turns. Spell
slots, factions, equipped clothing and dim map cells are initial setup data;
no fixture sets live invisibility, Hidden or truesight flags. A blocked Hide
has no fabricated canceled event and therefore yields an honest idle clip.
The observer's recording includes only its own inventory consumption. The
subject's own state and movement remain available while another actor cannot
see it. Search is not an existing native action and is outside this matrix.

Capture this unit with `python -m devtools.animation_review.capture --tag concealment`
or replay with `python -m devtools.animation_review --tag concealment`;
both commands include each experiment's two perspectives.
The potion uses the original authored Taunt/effect-frame-8 body track. Its
original drink strip is currently reported as an unbound media gap: both its
asset and the body-action media-track playback connection are outstanding; no
replacement VFX is generated for it.

Paired cards have **Show paired views** and **Export paired views** controls.
Each card still contains four synchronized camera corners. The two observers'
presentation durations can differ because they receive different parts of the
same native history; compare root identities and disclosure transitions rather
than treating equal video milliseconds as the same event.

September 11 validation: `runs/20260911T212148Z-a25e65` contains all thirty
visibility clips, 2,255 four-corner frames and 65 public history heads, with no
reported presentation gaps. A fresh process replayed saved player packets with
native production and content bootstrap unavailable. All thirty inputs, local
native diagnostics and MP4s matched their captures byte for byte; historical
states, heads and frame traces matched exactly. The inspection report preserves
the only raw trace difference: three subsequently added optional content
attribution fields now serialize as `null`. The original 72 inputs remained
unchanged. Source manifests retain the actual capture/render revisions; the
private native baseline fix made during rendering did not affect these inputs.
The fifteen-row native contact matrix passes, as do all seven gallery tests and
the existing lifecycle/healing gallery checks. A separate six-clip regression
run, `qa-player-boundary/runs/20260911T212720Z-acfe0a`, shows both participants'
walking/jumping lethal reactions and lethal displacement into the first spike
cell without replacing the historical inputs.

The `gameplay` tag includes the initial 15 creature/equipment/movement additions:
Dretch, Skeleton Archer and Wolf histories; actual weapon/wardrobe replacement;
melee then ranged through native Extra Attack in the same turn; turning routes
with ordinary movement, Haste and bonus-action Dash; multi-cell jumps over real
water, uphill, downhill and over the stair span; and a second-step native
reaction with continuation/death. Characters receive actual native apparel.
Haste/Dash allow extra legal distance at the existing authored animation rate.
Selected packaged rig JSON maps each native content identity and authored clip
name. Equipment and movement traces retain their original Studio contexts.
The two hill cards carry `known-occlusion`: rear-view terrace/cliff pixels still
cut through part of the airborne body. Their native/timeline checks pass, but
this is an explicit visual exception awaiting a shared terrain correction.

The active-set case starts with sword and bow, uses melee, unequips the sword
through the native equipment operation and then uses ranged Extra Attack.
The accepted equipment fact selects the surviving bow before that attack.
The original Taunt gesture changes the displayed set at authored frame 4;
same-set item replacements still settle their membership at body completion.
Two discovery cases reveal an actor during walking or a later deployment,
after it changed equipment and lost HP while unseen. The first received
appearance has its current dagger and 33 HP before a subsequent ranged attack.

Jump reactions now play as complete subtrees at the grounded visual launch
contact. A surviving jump then traverses its selected body clip once over the
entire flight; death/paralysis prevents takeoff. Walking retains its existing
edge interruption. The stable `jump-midflight-*` case IDs refer to the original
regressions; their titles and current playback describe the corrected behavior.
Five additional cards extend short/long direction comparisons, two
sequential reactions before takeoff, and a later-Step reactor. That last card is
tagged `known-reach-presentation`: native reach can become valid only at a later
Step, outside melee reach of the visual launch. The clip exposes this spatial
limit while preserving native eligibility, ancestry and committed endpoints.
If a later Step stops, legal and visual positions can differ; the existing
placement override keeps the grounded body stable across head completion.

Eleven forced-movement cards add native Shove success/resistance, full/partial
obstruction, no opportunity reaction, stair ascent/descent, a Goblin recipient,
spike entry damage/death and a granted Telekinesis displacement. The original
Kick contact launches the recipient's TakeDamage brace, eased travel and body
release. Original context JSON and the Studio preview's cue values remain data;
the trace includes both alongside the compiled path and reached-cell timings.
Actual spatial children apply their damage at the cell reached, within the same
lineage. Death retains the reached corpse position through release to idle.
Forced displacement neither spends voluntary movement nor synthesizes Steps.
The two stair cards carry `known-occlusion`: projected height is correct, but
the existing terrace painter hides much of the moving body in several views.
These are allowed native slopes, not a cliff-falling implementation. The
Telekinesis card starts with the real cast/grab already established and records
its granted Move action; it does not claim broader spell-delivery coverage.

The authored recipes, rig maps and recorded sequence are JSON data. A later
TypeScript frontend needs the corresponding decoder, presentation
reduction/sampling and render adapter; Python engine mechanics remain the
authoritative producer. Diagnostic traces accompany the executable input but
are not themselves the playback input. Local review files are developer
artifacts; their source manifests and diagnostics are not a player protocol.

## Review loop

1. Filter tags or case IDs. Play visible clips together, slow down, or step one
   frame. The four corners within each clip are always synchronized.
2. Mark **Issue** or **Approve**. Pin the relevant moment and write a note,
   including which corner looks wrong. Review verdicts are separate from the
   automatic checks and known media gaps.
3. Select cases and choose **Export selected traces**, or export a single
   card. The downloaded JSON contains the run/source identity, notes, video
   time, selected frame index, each complete trace and its saved input. Export
   fails visibly if a referenced artifact cannot be fetched or belongs to
   another run/case. A case that failed before input capture remains exportable
   as diagnostic evidence; it cannot be replayed without recorded input.
4. Give that JSON to the debugging agent. The selected frame resolves to the
   root UUID, historical clock, actual state and all four corners' draw evidence.
   The trace also includes the full retained baseline/event ancestry, condition
   UUIDs, authored compiled timings, source file hashes and automatic results.
   `run`/`sources` identify the renderer revision; the recorded input and
   `trace.input` retain the original native capture time and source manifest.

Reviews persist in browser storage per run. Export is the portable copy.
Generated runs are separate directories under `.runtime/animation-review/runs`;
a new run does not overwrite older clips or feedback. The root URL redirects
to the newest finished report. A failed case remains in the report with its
trace/error, and generation exits nonzero. A passing automatic check is not a
claim of visual correctness or full animation/media coverage.

Movement traces distinguish legal Step endpoints from rendered contacts.
Uncommitted walking/jumping reactions retain the visible stop position through
death/paralysis recovery and idle; the legal entity remains at its Step origin.
Each contact records `body_lift_px` separately from support elevation. Capture
checks legal endpoints, visual stop continuity and placement after releasing
the final head. All four views use the same placement state. Floating feedback
and name/HP labels share body-aware placement within the view below its header.
During a pause, the recorder compares each RGB frame directly with the first
held frame, releasing that reference when playback resumes. The
`frozen-presentation` check records this pixel equality together with retained
state and draw metadata.

## Repeat a focused step

```bash
uv run --no-sync python -m devtools.animation_review --list
uv run --no-sync python -m devtools.animation_review.capture --case 'walk-*'
uv run --no-sync python -m devtools.animation_review --case 'walk-*'
uv run --no-sync python -m devtools.animation_review --tag ranged
uv run --no-sync python -m devtools.animation_review --tag gameplay
uv run --no-sync python -m devtools.animation_review --tag forced-movement
uv run --no-sync python -m devtools.animation_review.capture --tag visibility
uv run --no-sync python -m devtools.animation_review --tag visibility
uv run --no-sync python -m devtools.animation_review --review /path/to/downloaded-review.json
```

`--review` renders the actual saved inputs embedded in the exported review.
It preserves original UUIDs, ancestry, case settings and capture provenance,
and does not consult native producers or require that the case still exists
in the current catalog. The new trace retains the original review's pin and
note under `review_origin`. Current renderer code and art are used; this is
not a code rollback. Old exports containing only lossy diagnostic traces are
rejected with an explicit explanation, never silently regenerated from IDs.

Ordinary `--case`/`--tag` runs select catalog entries and load their saved inputs.
If the catalog definition changed, the tool reports that it is using the saved
definition; only the explicit capture command replaces it. `--review` never replaces
the shared input collection.

Add cases as catalog data over an existing producer. A new gameplay family
should first gain a reusable public scenario, not a private gallery animation.
Keep the automatic checks and clips together; run affected cases after a step
and the full catalog at an implementation checkpoint. No image-diff baseline
is silently promoted by the tool.

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run --no-sync python -m pytest \
  tests/game/test_animation_review.py tests/game/test_animation_review_server.py -q
```

These verify real ranged/paralysis/cast recordings, frozen authored-map export, all four views, retained frame
and event identity, MP4 decoding/frame counts, visible capture failures and
HTTP seeking. Saved-input and exported-review checks repeat a recovery history
in fresh processes without native production/bootstrap, comparing historical
successors and sampled frames. Paired replay also compares the encoded videos;
pause checks compare rendered RGB bytes directly. Existing gameplay/encounter tests separately protect mechanics
and independent latest/historical progression.

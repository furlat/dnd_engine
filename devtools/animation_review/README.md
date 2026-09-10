# Animation clip extraction and review

From the repository root, using the existing virtual environment and installed
`ffmpeg`/`ffprobe`:

```bash
.venv/bin/python -m devtools.animation_review
.venv/bin/python -m devtools.animation_review.serve
```

Open <http://127.0.0.1:8767/>. The first command generates every case in
`catalog.json`; the second serves the local files, including the HTTP byte
ranges needed for browser video seeking. No game server or Node runtime is
involved. Capture uses SDL's dummy video driver by default and does not need
the desktop. MP4 is used for pause, seeking, frame stepping and efficient
parallel playback.

Each scenario executes once. Its complete retained lineages are reduced and
sampled through the same `game/playback_frame.py` function used by the game.
Each recorded instant is drawn from all four camera quadrants in one pass,
then encoded as a synchronized 2×2 video: 0/1 above, 2/3 below. Defaults are
24 fps and 960×640 per corner, giving a 1920×1280 clip. Use the video's native
fullscreen control to inspect the pixels. The state/condition rules stay in
the engine; this recorder adds no animation rules or gameplay queue.

The initial catalog covers 22 cases: melee profiles and outcomes, modular and
fixed-rig ranged attacks, ordinary movement, walking/jumping opportunity attacks
with save/miss/paralysis/death, paused retained playback, two-cast histories,
repeated targets, height and equipment roots. The paralysis rider is the
existing configurable native mechanic, not a weapon-triggered Hold Person
spell. The pause case freezes an offline presentation clock over already
reduced history; live independent controller progression remains covered by
the encounter integration tests.

## Review loop

1. Filter tags or case IDs. Play visible clips together, slow down, or step one
   frame. The four corners within each clip are always synchronized.
2. Mark **Issue** or **Approve**. Pin the relevant moment and write a note,
   including which corner looks wrong. Review verdicts are separate from the
   automatic checks and known media gaps.
3. Select cases and choose **Export selected traces**, or export a single
   card. The downloaded JSON contains the run/source identity, notes, video
   time, selected frame index and each complete trace. Export fails visibly if
   any trace cannot be fetched or belongs to another run/case.
4. Give that JSON to the debugging agent. The selected frame resolves to the
   root UUID, historical clock, actual state and all four corners' draw evidence.
   The trace also includes the full retained baseline/event ancestry, condition
   UUIDs, authored compiled timings, source file hashes and automatic results.

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

## Repeat a focused step

```bash
.venv/bin/python -m devtools.animation_review --list
.venv/bin/python -m devtools.animation_review --case 'walk-*'
.venv/bin/python -m devtools.animation_review --tag ranged
.venv/bin/python -m devtools.animation_review --review /path/to/downloaded-review.json
```

`--review` regenerates selected IDs from the current catalog/code. It is not
an executable replay format or an automatic code rollback. Original UUIDs and
retained events remain in the exported evidence even when a fresh run creates
new identities. The command, seed/setup and working-tree source hashes make
that distinction explicit.

Add cases as catalog data over an existing producer. A new gameplay family
should first gain a reusable public scenario, not a private gallery animation.
Keep the automatic checks and clips together; run affected cases after a step
and the full catalog at an implementation checkpoint. No image-diff baseline
is silently promoted by the tool.

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python -m pytest \
  tests/game/test_animation_review.py tests/game/test_animation_review_server.py -q
```

These verify real ranged/paralysis/cast recordings, frozen authored-map export, all four views, retained frame
and event identity, MP4 decoding/frame counts, visible capture failures and
HTTP seeking. Existing gameplay/encounter tests separately protect mechanics
and independent latest/historical progression.

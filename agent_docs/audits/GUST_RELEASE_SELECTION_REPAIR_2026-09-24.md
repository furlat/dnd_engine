# Gust maintained-loop release correction

The fresh Linux release exposed four real missing-media failures and one
independent test-oracle mismatch in `tests/game/test_gust_maintained_media.py`.
The correction changes selected assets and test inputs; Gust's mechanics,
choreography, source artwork, placement and playback clocks remain unchanged.

## Cause

The original VFX inventory treated every maintained field as a world-fixed E
bank viewed from four cameras. Gust's existing maintained renderer instead uses
`view_facing(facing_for_delta(geometry.direction, data), quadrant, data)` from its
received line geometry. Both parity sets of the eight directional banks are
reachable. This is not determined by which facing happened to occur in one
review clip or by a default `viewFacing` value.

The finite intro retained frames 0–251 for all eight banks. The incorrect
maintained selection retained 252–359 only for E/S/W/N. Consequently the fresh
SE/SW/NW/NE ZIPs lacked their legitimate 108-frame hold window and raised
`KeyError: component-00/0252.bin.gz` during ordinary axial playback.

The silhouette test also called `registered_media_samples` without its camera's
zoom when constructing the independent expected picture. The current registered
geometry contract separates physical scaling from camera zoom. The omitted
argument made the reference's world-space coordinates half their intended size
at zoom 0.5. Supplying `zoom=camera.zoom` restores the geometric comparison without
weakening its exact pixel equality. Related clock comparisons now pass the same
camera to their picture compositor rather than implicitly using quadrant zero.

## Exact repair

Added only source frames 252–359 for SE/SW/NW/NE: **432 existing packets,
136,227,724 source bytes**. Source-frame payloads remain unchanged inside standard
ZIP_STORED archives. Frames 360–431 remain unselected: the actual finite intro
and maintained clock never request them, and Gust has no removal asset.

Generated files under
`/home/tommaso/Dev/neurodragon_art-packed-media-20260924/game/assets/packed/area.gust_of_wind.v4/`:

| File | Previous bytes | Corrected bytes | Members |
| --- | ---: | ---: | ---: |
| `impact-SE.zip` | 34,050,725 | 53,773,329 | 252 → 360 |
| `impact-SW.zip` | 56,753,478 | 106,646,873 | 252 → 360 |
| `impact-NW.zip` | 54,674,701 | 101,130,749 | 252 → 360 |
| `impact-NE.zip` | 33,962,260 | 54,171,505 | 252 → 360 |

The complete source archive remains unchanged. Pre-correction ZIPs and metadata
are preserved under
`.runtime/asset-packaging-20260924/gust-hold-correction/before/`.
`manifest-replacements.json` beside that directory records the four exact
manifest replacements, byte counts and offline generated-output content IDs.
No runtime checksum or fallback behavior was added.

Reproducible offline metadata now includes the 432 original source rows/files in
the selected base, selection/production plans, media packing plan and packed
media result. Positive correction claims in
`.runtime/asset-inventory-20260924/corrections/files.jsonl` override the erroneous
archive-only claims when `reconcile.py` runs. The phase/owner scale records and
phase CSV were corrected accordingly. The immutable historical inventory copy
inside the original source archive is retained as historical evidence.

Corrected selected base: 53,051 files / 15,066,816,317 bytes. Corrected generated
media stage: 157 files / 2,398,102,578 bytes; 28,272 replaced media inputs.
The parent task installed the four corrected archives into private production
and the fresh Linux validation tree and owns final release manifest/install
updates.

## Validation

`test_native_line_directions_keep_every_maintained_frame_in_the_release` derives
Gust's direction from real recorded native axial/diagonal casts, uses the existing
facing and maintained-clock functions, and checks every requested ZIP member
through the ZIP directory. It failed on the omitted axial banks before repair.
It does not decode every payload, infer future geometry policy, or retain unused
tail frames.

Fresh Linux validation:

```text
uv run --no-sync pytest tests/game/test_gust_maintained_media.py -q --tb=short
10 passed in 9.24s
uv run --no-sync pyright tests/game/test_gust_maintained_media.py
0 errors, 0 warnings
```

This covers both cast geometries and observer roles, intro suppression,
maintained timing/looping, partial visibility/cleanup, exact full-disclosure
silhouette equality, and all actual hold-frame addresses. The final assertion
also explicitly establishes that an admitted-cell tuple is present before
checking it, allowing the test's existing geometric requirement to type-check.

Independent reviewer `cleanup_ecs` checked the sibling selection surface using
manifest and ZIP indexes: all other 17 packed phases retain their full declared
frame ranges at all eight facings; 29 maintained variants / 133 unique
asset-phase requests found no additional gap. This is an offline release check,
not a new runtime inventory system. Focused replay capture belongs to the parent
task after this corrected release is installed.

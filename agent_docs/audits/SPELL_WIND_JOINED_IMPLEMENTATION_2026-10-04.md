# Joined Wind implementation — October 4

Implementation and final four-case gallery are saved and inspected. Independent approval belongs to the parent reviewer. This is packet 7's approved joined Wind work, not completion of the isolated missile gust or the full spell plan.

## Source and production boundary

The unchanged accepted `wind-modular-395fcd168669/WindModules.gd` supplies <=CELL path subdivision, shared miter boundary normals, the three 9×25 vertex layers, continuous full-path arclength UV, original vertex waves, noise/gradient equations, 12 source triangular chips, two finite WindHit meshes, palette, two-second flow and one-second retirement. `devtools/export_wind_components.py` exports the exact original material textures/contact mesh and compiled shaders through Godot. All ten original source resources and five installed/private payload hashes were checked; source and numerical receipts are retained in `wind-joined-20261004/`.

`WindFlowMaterial` is a closed authored value on existing `WallAssemblyMedia.flow`. The selected Wind row in `world_bindings.json` points to `/wind/flow-components.json`. `wind_flow_media.py` reconstructs the accepted native geometry on the disclosed wall path and uses the existing triangle/depth compositor. It preserves actual XYZ for support, terrain, actor, cell-disclosure and Antimagic exclusion handling. It uses the established spatial UUID and application/removal dates; there is no new mechanical event, registry, timeline or per-spell executor. Original isolated RGBA/XYZ source banks remain preserved.

Current visible body contacts drive the original quiet parting equations. Body height uses the shared `body_elevation_steps`, including received lift. The original body-clearance dimensions remain the accepted human-source calibration; no new roster fit or rig-specific adjustment is claimed. The source's single-body equations are evaluated at the nearest received body, while finite formation accents are restricted to actual committed recipients.

`SpatialDamageContact(event_uuid, recipient, at_ms, formation)` is passive data on the existing `SpatialMediaLifetime.damage_contacts`. Registration reuses bound cast application results/HP dates and standalone DamageCue results/HP dates, with the existing presentation offsets. Only a positive, noncanceled result naming that exact spatial owner can add a row. Event UUID deduplicates; witnessed owner creation marks formation. Wind selects only its formation recipients still present among current visible anchors. Later crossing, cold acquisition and unrelated heads do not invent or replay a hit. The same retained datum supports the parent's Thorns contact work.

## Shared numerical reuse

Original donor texture/mesh records and the unchanged texture reader moved from the Finger consumer into `directed_surface.py`; Finger's original source behavior remains covered. Optional original vertex normals and colors travel through the same winning barycentric sample, supporting Ice/Force source materials without a second renderer.

The existing triangle sampler now batches up to 512 small triangles, retains the 262,144-sample temporary budget, uses individual clipped rectangles, and retains the single-large-triangle path and original last-triangle tie behavior. The original scalar comparison passed all 56 XYZ/UV/normals/ownership cases exactly. Comparing batch sizes 16/128/256/512 passed 192 exact comparisons including colors and all four views/front-back passes of the actual 22,640-triangle Thorns mesh. Dense Wind sheets improved about 2.3× versus batch16; Thorns about 3.85×. Large random triangles were essentially unchanged. These are bounded CPU measurements, not a real-time frame-rate guarantee.

The palette pass computes the accepted full-source fragment RGB, then retains each fragment's real alpha/XYZ for shared world occlusion. This preserves source operations and registration but does not claim pixel identity with Godot's whole-source framebuffer in every transparent overlap or arbitrary world composition. No screen stretch or invented corner art is used.

## Verification so far

- Final native eight-heading/corner, observer replay, lifetime and Wind contact scope: 22 passed.
- Final shared Wind/Finger/raster scope after batch512 and literal colors: 20 passed.
- The original 56 differential cases and 192 batch comparisons are exact; depth/attribute tests include all four cameras and nearer/farther selection.
- Real Thorns recipient replay proves exact owner/recipient/position, one row per disclosed committed positive packet and later contact dates after formation. An earlier caster-view fixture had no disclosed damage through opaque Thorns; its empty expectation was diagnosed and the meaningful recipient-view check passed. The earlier failing log is preserved.
- Source/private production payload verification passed. Final body-height/contact scope passed five tests; scoped typing passed with zero errors.
- Existing native fixture now moves through Wind while it is maintained and asserts no repeated formation damage. The old drawing test's offscreen default camera was corrected to focus the received effect; no runtime camera change was made.

The four saved native inputs (corner and diagonal, caster and recipient) passed in `.runtime/wind-joined-20261004/runs/20261004T094853Z-d27a3c/`: 136 checks, zero gaps, 1,416 decoded frames. Standard 640×480 views form a 1280×960 four-camera clip at 24 FPS. The parent's explicitly approved 500 ms settled review hold retains every native head and unchanged native sequence bytes; exact hashes/pacing are in `wind-joined-20261004/final-review-pacing.json`. Source animation clocks and original 144/32 FPS material registration are unchanged by review-video sampling.

Twenty selected four-camera images were extracted under that run's `inspection/`; formation, mature corner/diagonal geometry, recipient passage, retirement and clearing were inspected. Six images were opened directly for this checkpoint. The straight wall is correctly edge-on in opposing views. Ordinary passage retains the same HP and no repeated contact effect. Previous interrupted larger 960×640/32 FPS attempts and the stale-loader failure are preserved and are not passing gallery evidence.

Wind's actual `Postprocess.gd.txt` explicitly overrides the generic capture metadata with nearest-RGB palette selection. That policy remains unchanged; two authored pixels are registered as `2 * camera.zoom`. The shared helper's new CIE76/boost/energy-alpha options belong to the distinct Thorns source and are opt-in. Independent comparison proved 20 default-RGB cases byte-identical. Optional pre-depth UV admission on the existing sampler exposes a surviving farther fragment when the near source texel dissolves; four camera/order cases passed, with default scalar behavior still exact.

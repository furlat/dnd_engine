# Persistent surface residue artwork

`world_bindings.json` maps the native `residue.ashen` condition to the two
delivered scorch motif atlases. The floor/wall originals remain unchanged.
Source: environment task `23a9`,
`output/environment-sprites/PRODUCTION-FIREBALL-SCORCH-HANDOFF.md` and its
`burnt-environment/scorch-{atlas,wall-atlas}-concept-v1.png` files.

The atlases are motif libraries, not seamless tile replacements. The floor
painter samples overlapping, varied motifs from stable world coordinates at
32 pixels per tile. A connected occupancy mask fades only exposed boundaries
and concave corners; it does not fade every internal tile edge. Elevation groups
retain their actual support height. Normal alpha at 0.45 preserves floor grain.

Wall soot samples a continuous field along each boundary's own tangent. It uses
explicit recorded `surface_residues.faces`, never guessed neighboring floor
conditions. Only a camera-facing disclosed side receives its marks. Authored
face planes are shared data profiles bound to the actual wall, corner and door
resources. Multiply at 0.8 preserves the base sprite alpha and cannot brighten
or replace the material. Stone footing is excluded by the main face plane.
Open doors use their separate leaf planes and retain their recorded condition.

The mark is persistent state, so the field is stable under camera turns,
repeat hits and later observations. Unlike the detached prototype, it does not
invent an impact center from currently known cells, stamp radial streaks from
that guess, or clear at the next shot. An explicit condition removal restores
the original surface. The shared compositor owns when that state becomes
visible; this painter does not add a second clock or require native render cues.

The original prototype's per-impact envelope is not copied. After user review,
the shared compositor now reveals Fireball's actual recorded Ashen changes from
ground contact outward at the recipe's 10 tiles/second. This is discrete surface
state timing, not a new per-pixel reveal mask or a second painter clock. It uses
the disclosed contact rather than reconstructing a center from visible marks.
Unchanged old marks stay visible, including between repeated impacts; wall
removal/replacement after-values retain source order at one surface time.

The authored wall planes and fixed-rig target
anchors still need subjective review in actual gameplay clips, particularly
door rotation and adjoining corners. Marks currently use each tile's retained
support elevation, matching the other residue art; a tread-following stain over
a complete multi-tile stair sprite is not separately authored.

The blast compositor clips empty ground by physical propagation and admits the
reachable rear-wall silhouette at that wall's own painter depth. Each effect
pixel belongs either to ground or one receiving wall; ordinary foreground bodies
and structures keep their ordering. World-space rays to the receiving footpoint
prevent a nearer wall from admitting fire on a farther wall's elevated pixels.
This uses retained boundary geometry and actual sprite alpha, separately from
the persistent soot field. It does not use Ashen membership to infer current
contact. Both smoke and additive fire follow this rule.

Composition masks belong to the historical cast and retain at most four views.
They are reused across animation frames and between the two effect layers.
Soot preserves alpha, so its appearance does not invalidate the geometry masks.
Mixed front/rear composite corner sprites retain conservative full occlusion;
general stacked translucent-wall rendering is not claimed.

Decoded and projected residue derivatives share a 32 MiB session cache. Their
keys contain local occupancy, actual wall coordinates/faces, camera and light
treatment. No whole-map raster, source scan, hash audit, native rule query or
per-frame texture generation is used. During the short reveal, derivatives are
rebuilt only for newly changed local occupancy, within the same cache bound.

Validation: nine actual pixel cases cover four-camera floor state/removal,
four-camera near/far wall-face separation, continuity, varied world samples and
the cache bound. The existing 97 boundary/bloodied-spike rendering cases pass.
The four-view inspection image is `/tmp/ashen-four-corners.png`; it is a painter
diagnostic from retained facts, not a replacement for the native gameplay clips.

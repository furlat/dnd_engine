# Seven AoE surface exports — production integration

The user explicitly requested installation of the Godot production report at
`/home/tommaso/.codex/worktrees/1aac/dnd_engine/output/weapon-vfx/aoe-surface-export/production-report/REPORT.md`.
This supersedes the earlier pending-delivery note. The work is asset integration
and shared spatial composition, not new spell mechanics.

## Plan and boundaries

1. Install only delivery packets/manifests for Burning Hands, Gust of Wind,
   Thunderwave, Shatter, Color Spray, Sleep arrival mist and Ice Knife burst.
   Keep source captures out of production. Decode requested frames through the
   existing bounded cache; no runtime asset scans, hashes or source audits.
2. Extend existing packed storage with ordered component paths/pivots per facing
   and explicit coordinate scale. Keep raw XYZ separate from image treatment.
   Thunderwave has 18 source components at one origin, replacing redundant
   per-cell placement; contact times remain unchanged. Color Spray retains its
   existing display factor in both pixels and coordinates.
3. Reuse registered samples, SurfaceVolume and ordered world depth groups for
   cast media, projectile impacts and maintained Gust. Preserve projectile/hand
   sockets, source duration, Gust intro/hold/cleanup, Sleep's Zzz condition and
   Ice Knife's separate native burst lineage.
4. Record existing AoEShape propagation into cold spell facts. Connected spread
   belongs to Fireball; ordinary spells retain native line-of-effect. Explicit
   recording-boundary compatibility preserves older Fireball archives without
   a spell-name switch in rendering or live registry queries.
5. Clip samples below actual disclosed support heights. Missing terrain is
   unknown, not a global zero plane; compatible recorded progressive supports
   may supply interpolation. Owner-zero pixels never acquire invented geometry.
   Preserve raw artwork without spatial context; suppress unresolved coverage
   conservatively when physical clipping is active, including additive RGB.
   Gust retains its existing disclosed extent and maintained lifetime.
6. Test decoded color/geometry registration, fractional pivots, component order,
   coordinate scale, support/unknown policy and cold native replay. Produce
   four-camera caster/target clips covering the seven spells and representative
   walls, doors, corridor tails, Globe and raised support. Review full lifetimes,
   not only peak frames; preserve previous Fireball regression coverage.

## Reviews and author corrections

Anti-slop and ECS/anti-OOP reviewers approved this direction with the explicit
native-policy/archive boundary, shared component ordering, historical support
data and Gust disclosure/lifetime requirements above.

The author confirmed that Thunderwave packet positions and pivots already
include cell offsets; its manifest component order is authoritative. One track
now submits the 18 components at one origin; its original contact table remains.

Color Spray's pivot is its whole-spell ground origin, while its mesh root already
contains the reference body's hand displacement. Pure ground placement would
regress existing small/wide-body attachment. The author confirmed the exact
emission point: `nativeMeshStartXYZ`, measured from release-frame hand pixels.
The importer converts that point into the existing source pixel convention;
`emissionPointByFacing` subtracts it before applying the ordinary live hand socket.
The resulting difference translates RGBA and XYZ equally, leaving field size and
native propagation origin unchanged. No manual per-camera fitting was introduced.
The existing independent hand-centroid test still covers all facings, all cameras
and normal/smaller bodies; its .001px tolerance covers the original rounded SE root.

The author completed Color Spray revision `eight-facing-registration-v2` and
Shatter `distinct-camera-banks-v2`. Both corrected manifests and packet deliveries
are installed. Shatter's SE/SW/NW/NE now represent four distinct scene yaws. Sleep
and Ice Knife impacts declare phase `viewFacing: SE`, so their camera banks are
independent of incoming travel direction. Travel artwork and trajectories are
unchanged. Gust retains all 432 native samples, its 1750ms intro, existing
252–359 maintained selection and cleanup; this is not a newly authored seamless
indefinite loop.

The ECS reviewer found a real ramp-crest issue in the first support sampler:
one neighbor's gradient was applied to both halves of a tile. Four edge gradients
now follow only compatible observed neighbors, with no extrapolation across an
unknown edge. A 1/2/1 crest and an unknown opposite half have explicit proofs.
The anti-slop reviewer also reviewed the final dynamic attachment correction;
41 independent selected tests passed. No remaining review blockers.

## Validation / completion

Installed only seven delivery directories and their manifests under
`game/assets/aoe_surface`; source captures, pilots, web audits and hashes are not
runtime dependencies. `devtools/import_aoe_surfaces.py` performs this offline
storage/registration conversion. It does not change saves, damage, affected cells,
spell durations, damage/contact times or casting aura sockets.

- 211 relevant tests passed together, covering cold event/player replay, all
  three cast-media spells, Shatter, Color Spray hand attachment, Gust lifetime
  and disclosure, Globe, Fireball material ordering and bounded decoding.
- The expanded surface test file passes 15 tests. Five were added after that
  combined run (216 distinct tested cases total): attachment translation and
  four-camera actual Ice Knife late-tail packets at frames 180/288/360/420.
  Tests establish that below-floor source pixels really exist and clear both
  alpha and additive RGB. Flat/raised/negative supports, ramp crests, unknown
  ownership, fractional pivots, coordinate scaling and old archive policy are
  also covered.
- Pyright on `game`, `dnd/actions.py` and `dnd/spells/ice_knife.py`: zero errors.
- [Review gallery](http://127.0.0.1:8767/runs/20260923T183603Z-0c1ae2/index.html):
  26/26 cards passed, zero presentation gaps. Thirteen experiments, each with
  both subjective perspectives and four cameras. Existing saved inputs were
  replayed; the new corridor case was generated once through real Ice Knife
  actions and then decoded like every other recording.
- Clips include axial/diagonal Burning Hands, Thunderwave open/blocked, Gust
  axial/diagonal/blocked with maintained flow and cleanup, Shatter wall/raised,
  Color Spray, Sleep, protected Ice Knife and its unprotected corridor tail.
  The corridor capture covers the entire three-second burst (72 displayed
  samples at 24Hz, native indices 2..428), including its late falling particles.
  Four-view frames were inspected for emission, component order, support height,
  protection and the late corridor tail. No new human visual approval is implied.

Re-render this bounded review without executing mechanics:

```bash
UV_PROJECT_ENVIRONMENT=/home/tommaso/.cache/dnd-engine/venv \
  /home/tommaso/.local/bin/uv run --no-sync python -m devtools.animation_review \
  --tag aoe-xyz --width 640 --height 480
```

The seven spells retain their existing native line-of-effect policies. Fireball
alone retains its previously approved connected policy. Archive compatibility is
explicit at deserialization, not a spell-name rule hidden inside the renderer.
One surface owner per translucent component is still not a deep volumetric stack;
the source contract's limitation remains. Unknown pixels are retained for raw
art reference, and cleared conservatively when physical clipping is active.

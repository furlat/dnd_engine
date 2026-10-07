# Full GPU renderer migration — playtest recovery addendum

**Destination superseded during October 7 planning.** The human paused this
pygame/OpenGL implementation to design a direct PixiJS client and narrow network
server. See the [current network/Studio plan](NETWORK_SERVER_NEUROCLIENT_STUDIO_PLAN_2026-10-07.md).
The measurements, packing defects, accepted source rates, visual contracts and
GPU/readiness proof requirements below remain evidence. Instructions below to
retain pygame window/UI or exclude TypeScript describe the previous destination,
not the current proposal. No new migration is implemented by writing that plan.

Status: full implementation plan, revised October 7; **not an implemented migration**.
The human requested this full plan after the initial feasibility study. Sections
1–7 retain its evidence and correctness constraints; sections 8–14 specify the
complete delivery, code removal and integration with every other recovery fix.
Independent review of this expanded revision is recorded in the
[review receipt](audits/PLAYER_PLAYTEST_PLAN_REVIEWS_2026-10-06.md).
This is the rendering/preparation amendment to the
[playtest recovery plan](PLAYER_PLAYTEST_RECOVERY_PLAN_2026-10-06.md), not a new
gameplay project. Its P01–P31 complaints, native-engine recovery, historical
causality, controls, UI and real-display acceptance remain binding.

The human explicitly requested a first-principles pygame-ce/OpenGL study after
rejecting continued small CPU fixes, identified asset preloading, and asked to
make shader work reusable by a later PixiJS client. No TypeScript client or new
artwork is part of this implementation. Keep pygame-ce window/input/fonts.

## 1. Evidence that changes the approach

Private measurements are under `.runtime/playtest-recovery-20261006/`.
They are diagnostic workloads, not acceptance of the playable application.

| Observation | Consequence |
| --- | --- |
| Native Windows, 2560×1440, initial crypt and scripted pan/rotation: whole-frame p95 17.60 ms, p99 20.70 ms; maximum 154 ms. First draw 6.25 s, first window 1.50 s. cProfile was active for the warm sample. | Some early repairs help the small initial scene. They do not explain away later 30 FPS, first-use spikes or satisfy the full journey. |
| Real Windows Fireball profile: a worst sampled frame was about 495 ms, roughly 65 ms sampling and 430 ms drawing. Native operation about 177–223 ms; synchronous head preparation about 447–547 ms. | Rendering, media preparation and native execution are separate measured problems. |
| One 868×552 effect component becomes 159 copied pieces at 163 peer cuts, with 11.64 million bounding-box pixels processed. Another reaches 12.52 million. | Per-pixel world ordering is expanded into many temporary CPU images. A larger cache or faster final screen upload does not remove this amplification. |
| The cast profile performs gzip decoding during sampling; warmup skips storage-backed travel and only touches selected first effect frames. | “Loaded metadata” and “first frame cached” do not mean an animation is ready. |
| Recorders render fixed sample times and encode at a chosen FPS. | Smooth exported video is not evidence of real-time rendering speed or input latency. |

The proposed local sparse-band shortcut is withdrawn: independent review found
that changing which peer cuts apply can reverse translucent sibling order and
change complementary-frame grouping. No such shortcut is implemented.

### Private GPU and storage feasibility results

`gpu-proof/render.py` uses the original Fireball impact frame 29, four camera
banks, two components (normal/add) and 163 uniformly distributed depth cuts.
It uses resident raw RGBA/XYZ16/ownership8 textures, no per-frame pixel uploads.
These are deliberately dense synthetic cuts, not a captured complete encounter.
Windows reports NVIDIA RTX 5090, GL 3.3, pygame-ce 2.5.8, ModernGL 5.12.0.
After eight warm frames, GPU p95 is about 0.53 ms and CPU issue p95 0.29 ms for this
isolated workload. The single SE CPU reference partitions into 254 pieces and
takes about 312 ms in the retained final run. Final opaque-background color differs by at most one byte;
XYZ decode maximum difference is 9.54e-7, ownership values are exact. Present,
full scene, input, mixed frames, screen blend and picking are not certified by
this comparison. This is evidence for moving the operation, not an app-FPS claim.

The exact common color/XYZ GLSL functions also compile and run under a GLSL ES
3.00 wrapper in headless WebGL 2. Palette replacement and unchanged alpha match
exactly; ownership matches exactly and XYZ difference is below 7e-7. Matching
source colors in byte space matters: comparing normalized floats directly failed
in the browser while working on desktop. The probe now rounds source samples
back to their authored bytes before matching. Browser software rendering is a
portability check, not browser hardware performance evidence.

`gpu-proof/working_set.py` reads all 64 impact frames for SE/SW/NW/NE: **3,567,450,592
decoded bytes**, 632,914,618 archive bytes, about 5.32 seconds sequential read and
gzip decode. Largest packet is 28,440,904 bytes; one bank is about 0.87–0.91 GB.
This excludes travel, bodies, reaction media and retained world assets. Source
planes are not identical across 2×2 pixel blocks, so simply halving their
resolution is not a lossless resource optimization. Complete four-bank raw
preload is not yet an admitted residency policy; a scoped working-set/streaming
design must satisfy the readiness gate below without a whole-library preload.

Two bounded loading experiments deliberately retain only an active/pending packet:

| Experiment | Observed result | Interpretation |
| --- | --- | --- |
| One decode thread, new textures, one plane uploaded per 60 Hz frame | 256 packets in 29.43 s; frame work p95 2.67 ms, maximum 83.80 ms; worst allocation/upload 83.62 ms | This schedule cannot supply a two-second impact. A large “one plane” upload is not a safe frame budget. |
| Two preallocated/warmed texture slots, upload work attempted within 2 ms slices | Allocation/warm 22.74 ms; all packets 13.28 s; frame work p95 3.51 ms, maximum 65.57 ms; worst texture write 65.32 ms | Removing allocations helps throughput but does not establish bounded writes or sufficient supply. A time-budget loop cannot interrupt one long GL call. |

These experiments exclude full scene/UI and do not measure real input response.
The first pumps events without handling them; the second drains events but does
not exercise real controls or quit during decode. Neither proves bounded decoder
shutdown. Raw texture payload counters exclude CPU temporaries and driver memory.
Their open findings are part of readiness feasibility, not accepted streaming.
Next prove complete group/bank deadlines, prebuffer needs, allocation versus write
versus synchronization outliers, handled input and total working-set accounting.
Do not turn these prototype schedulers into production code.

The retained evidence set is `gpu-proof/runs/20261007-feasibility-01/`; its manifest
records source/script/shader/asset hashes and versions. No production art was
changed, downsampled or repacked for these experiments.

### Subsequent human corrections: packing and playback speed

The human rejects treating 3.3 GiB as a reasonable asset target and explicitly
chooses **keep 32 FPS; fix packing only**. The figure above is decoded source
payload across four banks, not archive bytes or a measured necessary resident
working set. Audit and repair waste before fixing residency budgets. Do not
solve it by assuming a larger GPU allocation is sufficient.

Installed Fireball travel is 12 frames at 24 FPS; its impact is 64 at 32 FPS
(two seconds). Other registered phase rates exist. Preserve existing lower/native
rates; do not normalize everything to 24 or raise them to 32. The packing work
changes no playback clocks. A separate P08 audit must inspect spells reported
as too fast and trace source duration, effective phase duration/time maps, cast
rate multipliers, projectile travel and contact/reaction milestones. Correct
proven timeline/assignment errors in existing owners; no global slowdown slider
used to conceal bad authored timing.

Initial packet inspection finds normal and additive components stored on one
shared rectangle even when one component is completely empty. Empty borders
and sparse tails also allocate full RGBA/XYZ/owner planes. Their overlapping
XYZ values are **not** generally identical, so sharing the normal component's
geometry with the additive component would be wrong. The complete audit must
quantify exact crops, zero/duplicate planes, bank/frame identity and sparse
storage without altering visible pixels, ordering bounds or registration.

Per-pixel XYZ has separate consumers: world ordering, physical clipping and
some authored materials. Absence of a gameplay collision does not prove all
three unnecessary. Separate lifetime resource admission from a cheap per-frame
consumer decision. With no depth-interleaving peer, physical cut or
XYZ-based material, emit an ordinary color draw: no XYZ expansion, world-depth
array or physical mask. If only depth is needed, evaluate depth alone in the
GPU; if clipping is needed, evaluate only admitted intersecting geometry. No
full CPU coordinate images in any branch of the migrated renderer. Validate
the fast path against the general path on unclipped, raised, overlapped and
boundary-crossing examples, so it cannot revive the known clipping defects.

Plane requirements belong to the derived readiness manifest over the complete
admitted interval, allowed camera views and concurrent persistent media—not just
the current overlap. Skip loading only if metadata proves no consumer in that
scope, or a proved preparation deadline makes the plane resident before first
use. Otherwise keep the resource admitted while skipping unnecessary evaluation.
Include global peer-cut, sibling and complementary-frame semantics in that proof.
Before admitting a later group, include any newly required planes of already
persistent effects. A fast path never starts a load or changes the ordering key.

## 2. Backend choice and portability contract

The implementation target is a pygame OpenGL context with a small ModernGL
adapter. G0 below must demonstrate the difficult composition and resource cases
before its concrete contracts are frozen; a successful textured quad alone is
not permission to switch production.

| Option | Assessment |
| --- | --- |
| Current Surface compositor with more cached derivatives | Keeps large CPU XYZ arrays, masks, material passes and split images. Useful as a temporary comparison oracle, not the selected recovery strategy. |
| pygame SDL Renderer with resident Texture objects | Provides accelerated transforms/composition; its documented API does not expose the custom shader operations required here. Useful comparison, not another permanent backend. |
| OpenGL window plus resident textures and shader programs | Moves work before the expensive Surface/NumPy boundary; supports authored material, geometry and composition operations. Requires an explicit transparency and picking contract. |
| Upload the finished CPU framebuffer to OpenGL each frame | Rejected: retains the measured bottleneck. |

Primary sources: [pygame display](https://pyga.me/docs/ref/display.html),
[SDL renderer](https://pyga.me/docs/ref/sdl2_video.html),
[ModernGL context](https://moderngl.readthedocs.io/en/latest/topics/context.html).
The installed pygame-ce is 2.5.8; current online pygame documentation is 2.5.9.
Validate actual APIs/capabilities in the installed environment; do not silently
combine a dependency upgrade with this migration.

Use shader operations expressible in the OpenGL 3.3 / WebGL 2 feature intersection:
vertex/fragment programs, ordinary/integer 2D textures, render targets and explicit
uniforms. Do not require compute shaders, SSBOs, bindless textures, geometry
shaders or desktop-only texture buffers. Baseline data textures use sized integer
formats and nearest texel access. Float-render-target requirements must be
separately capability-checked; WebGL 2 alone is not a promise of all such formats.

Keep common GLSL function bodies and resource specifications separate from the
small desktop `#version 330` and browser GLSL ES 3.00 headers/bindings. A later
PixiJS WebGL adapter can reuse those bodies, fixtures and units. PixiJS WebGPU
uses a different program language; WGSL translation would be later work, not
literal GLSL reuse. Do not add a shader transpiler or implement PixiJS now.
The same common color/XYZ functions must compile under desktop and GLSL ES 3.00
wrappers and pass representative fixtures in a minimal WebGL 2 harness. Desktop
compilation alone does not validate browser resource/format restrictions.
[WebGL 2 specification](https://registry.khronos.org/webgl/specs/2.0.0/),
[PixiJS shader resources](https://pixijs.com/8.x/guides/migrations/v8).

## 3. Ownership and concrete code boundary

Native engine → recorded public facts → existing reduction/timelines → sampled
presentation values → resource references/material parameters → GPU composition.
Only the final two stages change. The GPU never evaluates visibility, rules,
target legality, saves, reactions, event timing, suppression or damage.

`DrawCommand.surface` currently forces pixel construction before the compositor.
The replacement boundary must precede `registered_media_samples`, body material
rasterization, directed-surface rasterization and volume splitting. Merely
wrapping the current DrawCommand in a GPU uploader is not the final design.

Proposed small module structure; names are implementation destinations, not
permission to introduce a generic framework:

| Owner | Responsibility |
| --- | --- |
| `game/render_types.py` | Frozen resource/format, registered image/mesh, material, order, physical coverage and draw records. No pygame/ModernGL imports, no behavior methods. Use concrete tagged variants and existing authored types where suitable. |
| `game/media_resources.py` | Existing source resolution extracted into functions: file/archive/frame requests and immutable decoded payloads. One decoder for each existing storage format; no new asset registry. |
| `game/media_readiness.py` | Passive session residency/queue state and functions to request, pin, admit and release resources. Dependency enumeration uses the same selectors as sampling. |
| `game/gl_resources.py` | Context-owned textures/buffers/program handles, upload/delete and byte accounting. Imports portable records; never native entities. |
| `game/gl_draw.py` + `game/shaders/` | Concrete shader dispatch, composition passes and target management. No spell names, condition rules or new animation clock. |
| Existing sample/draw modules | Produce registered resource references and parameters instead of resized/materialized pixel arrays. Keep the current recipe selectors, placements and timestamps. |
| `game/encounter_play.py` and other entry-point compositions | Own decoder lifetime, GL context, readiness admission, input pump and native-worker connection. |

Static DAG: authored/public types → sampled records → resource/renderer functions
→ application composition. Native runtime imports none of these GL modules.
No late imports, entity subclasses, service locators, reflective fallback or
second event graph. Keep CPU reference code only through migration acceptance,
then remove its production dispatch and superseded image-derivative caches.

### Required record content

Resource identity: immutable source revision plus file/member/plane/frame/crop,
not Python object identity and not tint/zoom/time. Decoded payload declares byte
order, channel format, row stride/origin, dimensions and color encoding.

Registration: original canvas dimensions, crop offset, per-bank pivot, authored
scale/reference pixel scale, coordinate basis, XYZ bounds, owner-plane meaning.
Keep geometry/data planes separate from color: no sRGB transform, palette swap,
alpha premultiplication or smoothing of coordinate/owner bytes.

Draw: resource references, source rectangle, stable transformation, current
material parameters, opacity/blend, existing painter key and sibling/mix identity,
disclosed physical geometry reference/revision, visual and selection roles.
Do not serialize GL handles or Python Surface/NumPy objects into portable data.

## 4. Shader responsibilities and migration coverage

| Existing owner/family | GPU operation | Remains CPU/authored |
| --- | --- | --- |
| `registered_media.py`, projectile sample projection | UV/crop placement; nearest scaling; pivot rotation; XYZ16 and owner decoding; view transform/depth | Eight-direction bank choice and residual angle from the existing trajectory; motion/release/contact times |
| `spell_palette.py`, `item_effects.py`, finite/body materials | Exact source-color replacement, authored ramp lookup, material noise, opacity, glint/bloom | Palette tables and source luminance statistics prepared once, material selection and lifecycle |
| `directed_surface.py`, construction/thorn/wind media | Original mesh triangles, donor textures, authored material equations | Authored mesh/resource selection and admitted geometry |
| `volume_media.py`, `area_media.py`, spatial fields | Per-fragment support, barrier, exclusion and registered ownership tests | Public historical supports/barriers; resolved affected regions; authored physical transition moments |
| `fixture_depth.py`, boundary/terrain composition | Registered depth/coverage lookup, wall cutaway, apertures, world overlap | Existing public contact/depth and explicit layer semantics |
| `water.py`, surface residues, deposits | Water/material sampling and per-pixel residue coverage | Retained public deposition/support records and unchanged deterministic particle state |
| Particles, shadows, trails, portals, sustained/condition markers | Resident-image quads, transforms and authored blending | Current deterministic samples, marker playlist, portal timing and attachment sockets |
| UI/icons/portraits/text/grid/highlights | Resident icons, glyph/image quads, lines; target/selection masks | Existing layout, human labels, recorded log math, targeting/choice admission |

Preserve exact palette **swap**, not multiply tint. Hand/effect palettes follow
existing spell assignments. Lighting is a distinct material operation; do not
recolor UI icons with world lighting. Preserve authored ordering between body
materials and owned-item modifiers. Text remains antialiased, artwork nearest
sampled. Grid remains between receiving floor and walls, including raised floors.

No tile visibility mask may cut admitted Fireball/Sunburst/Sleep art into teeth.
Physical wall/floor/propagation clipping remains driven by public recorded facts
at the existing authored clearance moment. Loading never changes those moments.

## 5. Transparency is a feasibility gate

A conventional depth test only selects the nearest surviving fragment. It does
not reproduce smoke/fire over actors, faded walls, additive/screen layers or
weighted complementary animation frames. Never claim this is solved by enabling
GL depth testing. Weighted approximate transparency is not the default solution.

First compare two bounded implementations against concrete current contracts:

1. **GPU band evaluation:** preserve the current ordered peer-band and sibling
   composition; pass raw XYZ/coverage textures and band thresholds to shaders
   instead of constructing masked CPU Surfaces. Draw order and complementary
   frame grouping stay explicit. Measure draw-call/fill amplification. This is
   a possible first production path only if it meets the full frame targets.
2. **Per-pixel ordered composition:** depth peeling is a candidate if band
   evaluation is too expensive. It needs a complete ordering key, tie handling,
   blend operators and frame-mix semantics, not just a float depth attachment.
   Do not silently cap layers or discard overflow. Prove working-set cost and
   supported render-target formats before selecting it.

The current ungrouped fixture/terrain partitions use a covered-pixel **mean**
depth per band; grouped volumes preserve authored layer order within shared
bands. These are not identical to geometric per-fragment sorting. Explicitly
catalogue and resolve parity for these cases before changing the algorithm;
do not introduce a synchronous per-frame GPU readback to recover means.

Reference cases: intersecting translucent siblings with opposite depth order,
a small particle whose bounding box adds a distant cut, two XYZ volumes,
screen/add/normal/premultiplied combinations, complementary frames crossing an
actor, walls/windows/door apertures, raised support and shell exclusions.
Known-bad output is not a golden requirement; any intended correction gets a
specific before/after contract rather than hiding behind “GPU parity.”
[Depth peeling discussion](https://developer.nvidia.com/gpugems/gpugems2/part-ii-shading-lighting-and-shadows/chapter-15-blueprint-rendering-and-sketchy).

## 6. Asset readiness, not first-frame warming

Current lazy families include world/fixture/item/portal imagery, body sheets,
projectile packets and PNG parts, donor textures/mesh JSON, palette noise and UI.
Enumerate all of them through the existing selection functions. No separate
handwritten per-spell preload list. Enumerating a presentation group includes
intermediate reactions/cancellation/death poses, not only before/after actors.

Two preparation stages:

1. One bounded application-owned decode worker reads/decompresses sources and
   returns immutable RGBA/data/mesh payloads. Reuse existing startup preparation
   ownership. No GL/display/font calls there; the native worker remains separate.
   PNG decode must retain current byte/color semantics; compare decoder outputs
   before substituting a library. Prepare whole needed body source once, extract
   requested rows without decoding the same full PNG for each new action.
   The proof must select thread versus process from input responsiveness and
   bounded shutdown evidence; an existing ThreadPoolExecutor is not proof that
   an executing file read/decode can be interrupted.
2. Main context owner uploads prepared resources and compiles the bounded shader
   set while continuing to pump events. Budget uploads by measured bytes/time;
   one huge indivisible upload is still a stall. Texture allocation and uploads
   are separately timed. Allocation failure/malformed source is a named error,
   not missing artwork or a blanket caught exception.

Readiness stages are requested → decoded/validated → uploaded → resident.
“Ready” additionally means the required shader/targets and complete dependency
set are ready. Draw/sample never starts a load. A missing resident reference is
an informative invariant failure naming asset, stage and presentation owner.

Pin the displayed scene, persistent conditions/world effects, active presentation
group and admitted lookahead. Release transaction pins when its last sample is
retired; retained effects transfer ownership to the displayed scene. Unpinned
LRU entries alone may be evicted. Cancellation/death/new head must release
obsolete requests without releasing resources still shared by other owners.
Use one running decode job, bounded queued/completed payload bytes and immutable
resource-key deduplication. Request owners are separate from resource identity;
results carry application-session/content-generation tokens. Dispose stale
results without admitting them into a newer session. Pins also protect unfinished
uploads, with atomic transfer to retained scene ownership. Native cancellation
or death does not cancel preparation for its still-required historical samples.

Startup readies current visible scene/UI and needed idle/initial poses; prepare
reachable controlled actions and their reaction media during the responsive
loading/idle phase. An unexpected newly disclosed rig or spell queues preparation
before its presentation clock advances. Native eligibility is unchanged: media
readiness is not a new gameplay prerequisite and must not create fake disabled
actions. Keep native-command-to-playback latency visible and within the parent
plan's targets; hiding seconds of preparation behind a loading state is failure.
Speculative prefetch is bounded by already available public action choices; it
does not run new discovery or recursively search possible reactions.

Complete native replies continue reducing into `latest` while their original
presentation groups remain retained. Pending media does not dequeue/admit a
group, advance `historical`, reveal that group's HUD/log commits or establish
its lifetime origins. Already displayed media and UI keep their existing clock
semantics. Readiness admits once with one start time and unchanged relative
milestones. Never retry native execution on a preparation failure. Lookahead
preparation cannot mutate current facings, contacts or lifetime state.

Measure complete current/next-group and persistent working sets in all four
camera banks before selecting byte budgets. Count decoded CPU bytes, staging,
GPU resources, render targets and retained CPU pick geometry separately. Current
640 MiB projectile LRU and independent count-only caches do not establish that
bound. Sharing immutable source textures removes per-palette/zoom duplication.

If the finite admitted group exceeds the measured residency budget, stop that
design gate and specify a bounded streaming schedule before implementation.
No active-frame eviction, whole-library preload or unbounded allocation is an
acceptable fallback. Never stall inside a running effect because its next frame
was not prepared. Four-bank readiness prevents rotation from triggering decode;
camera pan/zoom changes parameters, not resource identity.

On resize: rebuild viewport targets only. On context recreation: new context
generation invalidates GPU handles, reupload retained decoded sources. Content
revision invalidation is separate from camera/world revisions. Explicit teardown
cancels unstarted requests, disposes completed unwanted payloads, closes archives,
releases GL resources before context destruction and joins the decoder without
an unbounded hidden executor wait. Report actual bounded shutdown limitations.

## 7. Picking and interaction must survive the change

Keep explicit selection/physical coverage distinct from displayed RGBA. A faded
wall, actor aura and door aperture do not have the same selection rule. Preserve
the existing aperture-before-ground preference and camera-independent authorized
interactable affordances.

The initial candidate keeps immutable source coverage on CPU and evaluates only
cursor candidates through their inverse transforms and shared public geometric
parameters; avoid a viewport-size CPU mask rebuild every frame. GPU selection
attachments may supply highlights. If GPU IDs are needed for final picking,
prove asynchronous readback/generation handling and immediate click semantics;
do not block every hover with `glReadPixels`, accept stale IDs, or use color alpha
as physical coverage. Selection parity is a mandatory feasibility result, not
cleanup left until the renderer is already shipped.
The point evaluator uses the exact last-presented frame's records, transforms
and public geometry, including nonselectable physical occluders, world cuts,
support masks and the selected composition order. It returns the existing
WorldHit. Retain presentation/camera/context identity with the interaction
snapshot. Preserve mouse-down/mouse-up ownership and native generation checks;
delayed GPU results must never retarget a gesture onto a newer frame. Include
resize, rotation, door clearance and arriving replies around a click in proof.

## 8. End state and explicit limits

Normal play, replay, native action reviews and saved-frame export use **one GPU
compositor and one resource-preparation path**. The existing authored recipes
still select motion, sockets, palettes, materials, layers and timing. Python
samples small values and issues draws; it does not build an RGBA/XYZ image of
each effect, resize it, recolor it and copy it into depth bands every frame.

Pygame-ce continues to own the window, input, clipboard, audio and font shaping.
ModernGL owns resident textures, buffers, material programs and composition.
CPU font rasterization on text changes, immutable image decoding, small geometry
calculations and point picking remain legitimate CPU work. “Full migration”
does not mean moving rules, event traversal or every scalar calculation to GLSL.

No new rules, native event schema, spell executor, animation timeline, material
authoring language, ECS, scene graph, generic render-backend interface, narrative
log or TypeScript client is introduced. No source artwork is repainted, reduced
in resolution or stripped of banks/frames. Existing recipe corrections in P08,
P09 and P16 remain individually traceable. The earlier UI design requirements
remain binding; this is not authorization to redesign them again.

The former Surface path may be used by migration comparison tools until G8.
It is not a user-selectable fallback and cannot silently handle an unported
effect. During development the current live renderer stays the default until
the GPU path covers all required families and passes the combined gates. Then
remove the old production dispatch. Do not merge two renderers on a per-spell
basis or upload the finished CPU world/UI framebuffer as the final solution.

## 9. Concrete contracts and execution model

### 9.1 Passive records, not a second presentation system

Extract the portable fields of the existing draw/sample contract into
`game/render_types.py`; keep `draw_commands.py` as the construction/sort owner
while callers migrate. Use frozen, typed records and a finite tagged union of
quad, registered-volume, mesh and overlay draws. Variant dispatch is exhaustive;
no untyped option dictionary, runtime reflection or callback stored in data.
Reuse suitable existing neutral types rather than copying their definitions.

| Record / value | Required fields and ownership |
| --- | --- |
| Source resource | Catalog/source revision, package-relative address/member, source frame/plane and subrectangle. Format, dimensions, stride, byte order, row origin and color encoding are explicit. No absolute-machine identity, palette, camera pan or GL handle in the key. |
| Registration | Original canvas and crop, authored pivot and bank, reference scale, XYZ bounds/basis, owner/footpoint interpretation. One registration applies to matching color and data planes. |
| Material parameters | Existing authored material identity, exact palette/ramp references, sampled strengths/time/opacity and relevant lighting values. Operation order is explicit; body effects and owned-item effects remain distinct. Time is supplied by existing playback, not a shader wall clock. |
| Placement | World support/contact and elevation, camera transform, local transform/pivot, residual rotation and scale. World units stay cells and five-foot elevation steps; authored registration units remain tagged. Convert in one place, not separately per spell. |
| Composition | Existing layer/painter key, shared-depth group, sibling order, frame-mix identity and weight, blend mode, bounds/scissor. Keep identity and ordering independent of diagnostic text. |
| Physical/selection input | References to already disclosed supports, boundaries, aperture/physical masks, exclusion regions and their historical revision; role/owner/cell and selection admission. Visual opacity is not the physical blocker mask. |
| Presented frame | Immutable commands, camera/viewport, presentation identity and physical-input revision. The displayed interaction snapshot refers to this exact frame. Context generation lives in runtime resource state, not recorded gameplay. |

Records must round-trip through the existing typed export/fixture approach using
finite numbers, explicit tags and package-relative resources. Add a versioned
render-contract fixture to `game/data/PRESENTATION_CONTRACT.md` and the existing
export tests; do not record every frame into a new permanent event stream.
Existing public recordings and catalogs retain their schemas unless a genuinely
new storage descriptor is needed. Any descriptor change has an explicit version
and a converter at the existing loading/export boundary, never in draw dispatch.

Static imports flow from neutral authored/public types to sampling and resource
functions, then concrete GL functions, then entry-point composition. Neither
native `dnd` nor the native worker imports ModernGL or the decoder. CPU picking
may share neutral transform/coverage inputs; it must not import the compositor.

### 9.2 Resource ownership and preparation

Keep resource resolution in `media_resources.py` and scheduling/pins in
`media_readiness.py`. Do not add separate caches per spell, camera quadrant,
enchantment color or UI panel. Actual source banks are distinct resources;
mirrored/reused banks share bytes. Zoom and pan change uniforms/vertices.

The inventory is generated from existing source selectors and catalog references,
covering scene, actors, held/dropped gear, UI and every intermediate presentation
sample. Sampling and dependency enumeration call the **same selection functions**.
The readiness manifest is derived runtime data, not a second authored catalog.
If a sampler discovers a new dependency after admission, fail with the resource,
group, phase and selector; do not load synchronously or omit the effect.

| State | Created/changed by | Retired/reset by | Persistence |
| --- | --- | --- | --- |
| Decoded immutable source payload | Source worker after validation | Unpinned budget eviction/content or session reset | Private installed/prepared source may persist; runtime payload does not enter recordings |
| Request and completion queue | Readiness owner, deduplicated resource request | Completion/cancellation; stale session/content token discarded | None |
| Pins | Displayed scene, admitted group, explicit lookahead owners | Atomic transfer to persistent scene or last historical use; never native death alone | None |
| GL handle/residency | Main context owner after full upload | Unpinned eviction/context teardown | None; context generation invalidates handles |
| Physical geometry packet | Existing sampled historical scene revision | New relevant geometry revision | Derived from public recording; no native private map |
| Pick snapshot | Successful presentation of a frame | Replaced after next successful presentation | None |
| Text/icon preparation | Existing UI content/layout/resource change | Bounded cache eviction/font/content revision | No new gameplay state |

G0 chooses **one** decode transport after testing it. First evaluate the existing
single decode-thread ownership because it is the smaller implementation. If
GIL stalls or bounded shutdown fail, use one isolated decoder process, separate
from the native worker, with bounded byte payloads and explicit transport
ownership. Document that choice before G2. Do not leave both transports or build
a general job service. For a process, use the same proven nonblocking-main-loop
ownership principles as `runtime_connection.py`; do not send large pickled
Surfaces, add a second native owner or block SDL on pipe reads.

Bound queues by bytes as well as count: one running source job, one completed
payload awaiting consumption, deduplicated lightweight pending descriptors. G0
sets the maximum source job and splits oversized sources at valid format
boundaries, not arbitrary compressed-byte offsets. Count all transport copies,
decoded planes and staging, including an in-flight upload that remains pinned.

Priority is displayed/active group, next retained group, newly required scene/UI,
then speculative controlled-action preload. No speculative job can starve a
committed group. Stop submitting speculative jobs once its reserved allowance is
used. Cancellation removes only unneeded owner references; historical effects
from a canceled native action are still required if their events were recorded.

The memory contract has separate byte limits for decoded/staging data, immutable
CPU pick coverage, GPU source textures, reusable composition targets, and UI.
G0 records numerical limits from the complete workload; allocation is checked
before submission. Report driver/process memory separately from logical payload
bytes. Stable-key deduplication and unpinned LRU eviction are the only normal
reuse policy. No `id(surface)` keys or count-only global cache chains survive.

### 9.3 Large effects: preparation has its own delivery gate

Default admission preloads the entire finite required group in all four camera
views plus persistent scene dependencies. This is the simplest correct path when
the measured working set fits. It must meet startup/command-latency targets,
including a player casting immediately after launch; idle time is not guaranteed.

For groups that cannot satisfy that bound, G0 must prove a scheduled resident
window before selecting it for G2. Its manifest gives resource first/last-use
times, all banks, byte costs, upload deadlines, available staging slots and a
minimum prebuffer. The schedule includes complementary adjacent frames, active
scene, reactions, death/cancellation and the next retained group. Retire a source
only after its final possible sample. Reuse texture storage only after previous
GPU use is complete; do not obtain apparent speed by overwriting in-flight data.

Derive the window from measured service times and concurrent frame work, then
exercise the worst complete workload and camera changes. A missed admitted
deadline is a diagnosed readiness failure, not permission to stall the clock,
drop a frame/effect, change bank or lower quality. If no schedule meets the
contract, the migration gate remains failed and must be repaired before rollout.

Lossless storage preparation is in scope where source decompression is the
measured obstacle. Extend `devtools/pack_media.py` and the existing installer
with an indexed, independently addressable prepared-plane variant only if G0's
comparison demonstrates its need. Preserve every selected RGBA/XYZ/owner byte,
duration, crop and pivot; verify round-trip hashes. No lossy GPU compression or
discarded XYZ axis. Compare original compressed packets against prepared
unaltered planes for cold/warm I/O, decode, transfer and total disk/memory cost.
Choose one storage route per registered family; do not install a speculative
duplicate of the entire library.

Prepared binaries and receipts belong to the private production-art/install
flow in `ASSETS.md`, never tracked game JSON or a runtime startup repacker.
Originals remain untouched. An explicit install/preparation command updates the
selected private release. Normal startup neither scans/rebuilds the library nor
silently falls back to the slow source representation if a required companion
is absent. Its error names the missing release/resource and repair command.

### 9.4 Frame scheduling and historical correctness

Each live frame: drain SDL input; accept complete detached native/decoder replies
without blocking; reduce native replies to `latest`; update existing input and
camera state; perform bounded preparation; admit at most the next ready
presentation group; sample the displayed history; compose GPU world and UI;
present and publish its matching pick snapshot. Record work and wait separately.

No group clock, event/HUD/log commit or lifetime starts while that group is only
preparing. Once admitted, all relative release/contact/clearance/condition times
remain authored. Already displayed persistent effects retain their own existing
clock. A preparation failure never resubmits a native action. Pending native
commands, resource readiness and playback are three different states; do not
collapse them into one flag that disables the entire UI.

Palette programs compile before first use. Active image/data resources never
allocate, decompress or upload from a draw function. A proved streaming schedule
uploads through the separate preparation phase, never from a missing-frame
branch. Small per-frame vertex/uniform updates are expected and measured; static
geometry changes only with its owned revision. Camera translation does not
rebuild textures, world cut masks or a whole viewport-sized CPU picker.

### 9.5 Composition and material contract

Use GPU evaluation of the current shared-depth bands as the first implementation.
Pass band bounds to original resident images/meshes; preserve peer-cut sets,
sibling order and the existing tie key. Coalesce adjacent compatible draws only
when order is unchanged. Do not regroup all additive or same-texture effects
across intervening actors/walls. Scissor to conservative projected bounds.

The contract table in G0 must resolve covered-pixel mean keys for ungrouped
fixtures/terrain, including dynamic clipping. Immutable source depth summaries
may replace image copies, but any CPU reduction cost must be measured on moving
and breaking geometry. A full per-frame CPU mask pass or synchronous readback to
sort GPU results defeats this migration. If exact band semantics cannot meet
budget, evaluate the ordered-composition alternative in section 5 **before**
dependent ports; document the selected semantics and remove the rejected path.

Shader passes have finite concrete jobs:

- Quads and meshes: projection, pivot/crop transform, nearest artwork sampling;
  raw integer XYZ/owner lookup with explicit origin/endianness conversion.
- Materials: source-color replacement and authored ramp/noise/effect equations;
  sampled body/item/lighting parameters, with the existing operation order.
  Preserve byte-color behavior and explicit linear-light operations individually;
  enabling sRGB globally would not preserve the existing art.
- Physical coverage: provided support heights/slopes, registered apertures,
  barriers, propagation and spherical/shell exclusions. These are pixel tests
  against public inputs, not new gameplay queries or tile-fog clipping.
- Composition: normal, additive, screen and premultiplied operators. Document
  straight/premultiplied entry/exit at each attachment; no double premultiplication.
  Preserve screen on transparent as well as opaque destinations.
- Complementary samples: accumulate original weighted alpha/color within the
  same authored mix group **and depth band**, normalize as specified, composite
  once. Keep the original unowned fringe's separate ordering. Reserve/reuse
  bounded scratch targets; no flattening an entire effect across an actor.
- Existing shadows, glow/bloom, cutaway and outlines: retain their authored
  extent and color. Do not add a new global bloom treatment to hide mismatches.

Do not assume one hardware blend function covers every existing operator.
Where destination sampling is necessary, use bounded reusable intermediate
targets with explicit pass order; no texture feedback loop reading the currently
written attachment. Validate desktop and WebGL 2 attachment/format capabilities.
No normal-play framebuffer readback or GPU `finish()` per frame.

### 9.6 Picking, highlights and UI

The chosen first picking implementation is CPU **point evaluation**, not CPU
viewport rasterization: broad-phase projected bounds followed by inverse
transform, exact source physical/selection coverage, public cuts and composition
order at the cursor. Include nonselectable occluders. Meshes use ray/triangle or
equivalent point projection against the same admitted geometry. G0 must prove
the algorithm handles mean-depth ordering, faded boundaries and mixed samples.
Shared immutable data is acceptable; a second scene model or rules path is not.

Use GPU mask/outline draws for Alt, hover and targeting, respecting the same
physical/selection contract. The highlight cannot make a hidden object visible
or obscure an aperture. Ground grid, AoE and path primitives use real supports
and sit after floor but before walls/actors. Mouse-down owns the displayed hit;
mouse-up still validates gesture and native generation. Camera/resize/replies
between them cannot turn the click into a different action.

Existing UI modules retain layout, input regions, text content, tooltips and
recorded math. Convert their image/primitive drawing functions to small typed
screen-space commands: image/text-run quads, clipped fills/borders/lines. Do not
build a new widget hierarchy, markup engine or framework. Cache antialiased
**shaped text runs** with font/size/style/content keys; do not replace kerning
with sums of individually measured glyph widths. Pygame rasterizes a changed
run once; GPU draws its cached alpha/color texture. Evict unneeded runs by bytes.

Keep accepted icon/portrait images resident at original colors, nearest-sampled
at the existing intended scales; no world lighting/tint on UI. Glass panels use
their existing translucent treatment. The log can scroll using cached layout
and text commands without repainting/uploading a full panel every frame. Clipboard
copy still reads the admitted log model, not rendered pixels or a second log.

### 9.7 Platform, capture and failure lifecycle

After G0, add the selected ModernGL version to `pyproject.toml`/`uv.lock`; validate
locked native Windows and Linux environments. Keep pygame-ce 2.5.8 unless an
identified API defect requires an explicitly documented version change. Do not
combine this with unrelated dependency upgrades or a Windows security bypass.
If a new PNG decoder is selected, validate exact bytes and declare its production
dependency instead of relying on a dev-only package.

Open the pygame `OPENGL`/double-buffered window early, show a responsive loading
frame and compile the small required shader set. Check renderer/vendor, minimum
GL version, integer textures, target formats, dimensions and sampler limits.
Fail with an informative capability/resource message; no silent CPU fallback.
Handle framebuffer versus window size consistently for high-DPI mouse positions.
Use vsync where available and measure actual presentation/wait; do not busy-spin
or count an intentional wait as a rendering cost.

Resize rebuilds only size-dependent targets and UI layout. Context recreation
invalidates handles and enters explicit re-preparation from retained/installed
sources before resuming historical playback; it never replays native commands.
Quit/reset cancels speculation, drains/discards obsolete completions, joins the
decoder with a tested bound and destroys GL resources before SDL teardown.
Exceptions retain resource, phase, source revision and presentation identities.
Catch only at ownership/transport boundaries to report and clean up; do not
convert renderer failures into missing sprites or a successful frame.

`game/encounter_play.py`, `play.py`, `demo.py`, `reference.py`, replay entry points
and `devtools/animation_review/capture.py` must use the same compositor/preparation
functions. Screenshots read the actual rendered target at an explicit capture
boundary. Recording may read back offline frames; live recording is separately
profiled and must not force a readback when capture is disabled. Capturing four
cameras uses independent frame views and shared source resources; it must not
mutate live picking or event timing. SDL dummy is not an OpenGL test backend:
keep pure contract tests headless and use an explicitly provisioned real/hidden
GL context for pixel tests. Headless CLI flags must not silently select old art.

## 10. Delivery packages, dependencies and removals

Every package has a read-only anti-slop/performance review and an independent
anti-OOP/ECS/causality review before dependent work relies on it. Findings are
fixed in the same package and the evidence receipt identifies the reviewed diff.
These are local reviews only; no other-chat communication. Implementations stay
in the shared branch and existing dirty work is preserved.

### G0 — repair source waste, close decisions and freeze the renderer contract

Inputs: measurements in section 1, existing draw/media owners and the parent
plan's real native-operation corpus. Deliver a checked-in small coverage/decision
table and private reproducible proofs, not prototype code wired into production.

First complete the packing/timing audit in section 1. Rank installed, actually
selected assets by disk bytes, dense decoded bytes, useful coverage and concurrent
resident need; distinguish source-export catalogs from runtime bindings. Build
lossless candidate output through existing packet/atlas packing, verify every
selected bank/frame/plane and logical ordering extent, then measure it through
the existing sampling and future GPU proof. Install a packing repair only after
registration/composition parity and private release verification; never replace
the source archive in place. Do not introduce a format solely to store an empty
component that existing component registrations can express. Sparse storage that
requires a new address table must justify its added draw/lookup cost before use.

The timing audit reports effective source/playback ratio for all bound spell
phases, with reasons for intentional retiming; inspect real motion/release/
travel/impact/recovery and condition transitions in normal live playback. Resolve
outliers through existing recipes/time maps or a demonstrated shared timing bug,
not resampling art or multiplying every phase's speed. Preserve recorded damage
and clearance causality. Publish a compact before/after case list for actual
repairs, including early/late/near/far projectile cases.

| Decision | Required experiment | Gate output |
| --- | --- | --- |
| Ordering | Captured peer cuts with crossed translucent components, sparse peer, two volumes, animated/broken fixtures, clipped terrain and apertures; normal/add/screen plus complementary frames | Selected ordering algorithm, fixture-mean treatment, tie/mix rules, all-view pixel differences and full-scene cost. No unjustified replacement with nearest fragment. |
| Picking | Same frames, including faded walls, nonselectable occluders, upper floors and door holes; click during rotation/resize/native reply | Exact hit/occluder results, presented-frame binding, point-evaluation cost; no synchronous full-screen readback. |
| Conditional data planes | Start color-only, rotate/add an already-recorded overlap or physical transition, then admit a new group affecting a persistent effect | Conservative lifetime plane admission, unchanged pixels/picks/global cut and mix semantics, no CPU XYZ images or late resource/deadline miss. |
| Read/decode/upload | Repaired packing first; complete Fireball and overlapping persistent/next-group dependencies, four views; immediate first cast, rotation during effects, large PNG and late creature reveal | Exact byte limits, per-call upload chunk/allocation policy, finite-group vs streaming selection, prebuffer/deadline evidence. Attribute 65–84 ms upload outliers rather than hiding them in a loop budget. |
| Decoder | Real controls and quit/reset while a long read/decode is active; transport byte accounting | One selected transport, shutdown limit and measured input latency; ownership of every pending/completed byte. |
| Storage | Original compressed vs lossless prepared planes if decode misses deadlines | Explicit selected storage descriptor/release, round-trip equality and disk/I/O/transfer cost, or evidence original storage meets targets. |
| Platform | Desktop GL and minimal WebGL 2 wrappers for selected operators/formats, not only palette/XYZ | Supported format/capability list and reference fixtures; no claim of implemented PixiJS integration. |

Also enumerate every production pixel producer/loader/caller against G3–G7 below.
The inventory must classify all draw variants and catalog registrations, including
currently unexercised ones, by existing selector, source format, operator,
registration, blend, picking role and acceptance case. Counts/identity sets are
derived, not maintained as a competing spell list. A missing row fails coverage.

Both reviewers must accept the selected decisions before G1. The earlier
feasibility-only approvals do not satisfy this gate. If a candidate fails,
revise that bounded decision and retest; do not silently lower the parent targets
or start porting families on a knowingly incomplete contract.

### G1 — passive draw records and shared dependency selection

Depends on G0. Introduce `render_types.py`; extract reference-returning selection
from `animation_draw.py`, `registered_media.py`, `cast_media.py`, world/item/UI
loaders. Convert source/registration/material values at their existing boundaries.
`media_resources.py` resolves addresses and decodes only validated source formats.
Do not introduce separate loaders for prefetch, playback and export.

Compare references, placements and sample times for the complete authored catalog,
native actions, motion, reactions, conditions and environment transitions. Test
round-trip portable fixtures and the static DAG. Removal: overloaded
`DrawCommand.evidence` as rendering input, Surface identity as asset identity,
duplicated frame/bank selection in preload code. Keep CPU pixel output only as
the temporary comparison adapter, not as an input to the new GPU records.

### G2 — bounded resource readiness and installed storage

Depends on G1 and G0's measured choices. Implement decoder ownership,
`media_readiness.py`, `gl_resources.py`, source pins, generation checking,
bounded queues and upload scheduling. Apply the selected lossless packer change
only if required by G0; verify the private install manifest without overwriting
authored recipes. Retain full body source once for multiple action-row requests.

Integrate group admission in `encounter_play.py` and common review preparation.
Validate late rig reveal, death/cancel branches, two waiting groups, context
reset and quit. Diagnostic source-read/decode/upload counters must be zero from
admitted sample/draw calls; streamed preparation must meet its separate schedule.
Prove the conditional-plane transitions in G0 again through actual group admission:
new groups prepare any new data needs of persistent media before starting; a
per-frame color-only branch never changes resource readiness.
Removal: first-frame-only `preload_cast_media` assumptions, synchronous
storage-backed frame misses, repeated full-sheet decode, unbounded global source
and transformed-frame caches. Do not delete a cache until its final caller moves.

### G3 — GPU foundation, terrain, boundaries and selection

Depends on G1/G2. Implement context, shader lifecycle, reusable targets, the
selected ordering/blending path and point picking. Migrate terrain, environment
fixtures/devices, doors/windows/destruction/apertures, grid and wall cutaway.
Owners: `app.py`, `assets.py`, `environment_draw.py`, `device_draw.py`,
`environment_art.py`, `device_art.py`, `fixture_depth.py`, `floor_composition.py`,
`boundary_occlusion.py`, `interaction_frame.py`, `projection.py`.

Validate all four views, supported zooms/fractional pan, raised/slope supports,
doors open/close/break, retained light, faded-wall click-through, Alt/Ctrl and
threshold floors. Selection is tested together with pixels, not later.
Removal: per-frame CPU terrain/fixture cuts, viewport-sized selection masks,
depth-band Surface copies for these families and grid list-tail slicing.
Keep projection/physical rule functions where still needed for point evaluation.

### G4 — creatures, equipment and attached materials

Depends on G3. Migrate modular layers and fixed creature sheets with their
original pivots, scale and animation contract; palette/Magic/Effect materials,
body conditions, owned weapon coatings/enchants, shadows, contours and trails.
Owners: `animation_draw.py`, `animation_data.py`, `body_effects.py`,
`finite_material.py`, `item_draw.py`, `item_effects.py`, `item_appearance.py`,
`weapon_trail_media.py`, `motion_media.py`, `interruption_draw.py` and the existing
attachment/sustained sampling functions. Retain authored samplers; replace pixels.

Validate modular and fixed rigs, approved wolf scale, facing/flight, prone→death,
hand/socket release, coating equip/drop/pickup, body material × owned-item order,
suppression/expiry and multiple overhead markers. No new animation assignments.
Removal: CPU recolored/resized body/item variants and per-frame NumPy materials;
do not remove pose/lifetime logic simply because its old output was a Surface.

### G5 — all registered spell and interaction media

Depends on G4. Port registered color/XYZ/owner/footpoint packets and paged PNG
banks through the same transforms/materials. Include projectiles, beams,
multi-ray/chain paths, finite areas, maintained clouds, condition application/
hold/release, concentration, summoning/despawn and portals. Existing owners:
`registered_media.py`, `projectile_media.py`, `area_media.py`, `volume_media.py`,
`cell_media.py`, `stationary_media.py`, `maintained_media.py`, `concentration_media.py`,
`spatial_field_media.py`, `spatial_contact_media.py`, `portal_draw.py`,
`orbit_media.py`, `particle_media.py`, `mechanism_projectile_draw.py` and their
existing lifetime/placement functions. G0's inventory resolves any additional caller.

Validate bank plus residual tangent rotation for **every projectile family**, all
views/heights, crop/pivot identity, beam endpoints/hand origins, complementary
samples, hit/miss/repeated/chain recipients and authored speed. Include Fireball,
Sunburst and Sleep continuous fringes at a disclosure edge; doors clear only at
their recorded animation milestone. Inspect actual pixels, not just angle values.
Removal: transformed XYZ/owner/footpoint arrays and Surface volume splitting;
archive reads from sampling; duplicated shader-vs-CPU palette semantics. Preserve
all authored recipes and native target/affected-region computations.

### G6 — mesh materials, walls, surfaces and aftermath

Depends on G5. Migrate directed mesh/donor-texture paths, construction/breaking
walls and domes, thorns/wind, plasma/solar geometry, water, deposits, residues,
dust and spatial responses. Owners: `directed_surface.py`, `directed_mesh_media.py`,
`directed_plasma_media.py`, `wall_assembly_media.py`, `wall_media.py`,
`thorns_surface.py`, `wind_flow_media.py`, `water.py`, `surface_residue.py`,
`residue_media.py`, `deposit_draw.py`, `object_dust.py`, `spatial_response_draw.py`.

Upload original meshes and immutable donor textures once. Evaluate authored UV,
normal/noise/palette/time equations in the shader; CPU emits geometry/parameters
only. Preserve scalar particle simulation/determinism and original material clocks.
Validate wall lengths/turns/rings/domes, support and XYZ exclusions, destructible
sections, overlapping residues, water and post-combat blood/death at all views.
This ports existing surfaces; the separate future surface-interaction expansion
remains excluded. Removal: Python triangle rasterization, per-frame full-image
water/material/residue operations and their transformed-image cache chains.

### G7 — complete UI, entry points and capture

Depends on G3–G6; simple loading UI can use this same path earlier. Migrate
`ui/primitives.py`, `media.py`, `skin.py`, `rich_text.py`, `combat_log.py`,
`action_bar.py`, `variants.py`, `panels.py`, `hud.py`, `targeting.py` and remaining
existing UI draw callers. Reuse their layout/content and gesture ownership;
rectangles, line geometry, image and text runs are render data, not new widgets.

Finish all application/review entry points listed in 9.7. Update capture from
`pygame.image.save(screen, ...)` to explicit final-target capture through one
helper. Preserve PNG/video orientation, alpha, timestamps and real frame traces.
Recorded playback after a native reset produces the same authorized outcomes.
Old recordings remain readable at their established compatibility boundary.

Validate inventory/equipment changes, long/log-copy/scroll/dice, multi-row bars,
hover variants/upcast/conversion, disabled/self actions and every minimal-layout
requirement at 720p/1080p/1440p. Validate resize/fullscreen and mouse coordinates.
Removal: production CPU world/UI panel compositing, redraw-and-upload-every-frame
text/panel path, recorder-specific alternative rendering and display-dependent
`convert_alpha` assumptions in general data loaders.

### G8 — remove old pipeline, finish remaining recovery and accept

Depends on G0–G7 and the native/input work in section 11. Delete unused Surface
compositor dispatch, transformed-pixel caches, old selection rasterization,
obsolete CPU blend/material/mesh implementations and test-only compatibility
shims that no longer protect a public contract. Shared mathematical helpers may
remain; legacy full renderer does not remain a maintained backend. Preserve
small reference fixtures/error maps instead of copying the old renderer into a
second permanent test implementation. Remove obsolete imports/dependencies only
after searching all callers, including tools/tests.

Normal startup selects the GPU renderer with no per-spell fallback. Run the full
combined acceptance below and both final reviews. Reconcile every complaint and
the complete family inventory with its result, remaining source/art dependency
and removal status. Do not claim recovery complete from a passing Fireball,
synthetic shader, seven clips, green unit suite or reviewer plan approval.

## 11. Integration with the other recovery work

This addendum replaces the **implementation of parent step 3**, and its affected
renderer/startup rows, not the other steps. Parent step 0's native/startup audit,
step 1's party/knowledge/path fixes and step 2's single native worker continue to
completion under their own acceptance. G0 uses their retained public data and
does not expand native packets to carry private geometry for renderer convenience.
Parent steps 4–5's input/event/recipe repairs are prerequisites for G8.

| Complaint | Fix owner still accountable | Migration integration / closure evidence |
| --- | --- | --- |
| P01 | Native topology/occupancy/path invalidation | G3/G8: two opened doors, occupied corridor, reach exact destination; record termination reason |
| P02 | Native preview/submission route identity, UI preview | G3/G7: displayed route and executed steps agree, including ally transit |
| P03 | Native traversal vs endpoint occupancy | G8: walk through ally, reject occupied final cell |
| P04 | Historical cutaway and physical picking | G3: automatically fade walls covering admitted visible supports, correctly pick through them |
| P05 | Native/import/startup audit plus source preparation | G0/G2/G7: real first-window/playable timings; no startup repack/whole-library scan |
| P06 | Entire renderer/preparation loop | G3–G8: real idle/pan/rotation/return frame percentiles, not recorder FPS |
| P07 | Public initiative/portrait binding | G4/G7: every visible enemy and controlled actor has the correct delivered portrait |
| P08 | Shared projectile bank/tangent/registration and authored timing | G5: all projectile families, directions/elevation, release/travel/contact/playback speeds |
| P09 | Authored palette selection and exact material operators | G4/G5: matched hand/spell pixels, body/item order; no multiply tint |
| P10 | Native selection-preview geometry plus UI | G3/G7: circles/cones/lines/walls, repeated/partial targets and impact on real supports |
| P11 | Existing frame diagnostics/HUD | G7/G8: compact truthful FPS and frame time, no text flood |
| P12 | Locked Windows environment/launcher | G0/G7: native Windows GL run, same art, security issue diagnosed without disabling protections |
| P13 | Native door incident-cell reach/discovery/approach | G3/G8: only the two incident cells operate an edge door |
| P14 | Historical physical coverage and registered-area shader | G3/G5: whole admitted effect, no fog teeth; physical wall/door clearance at authored time |
| P15 | Existing camera controls/projection | G3/G7: both zoom directions, cursor anchor and correct picks; no decode on zoom |
| P16 | Weapon/action/rig selection trace, not assumed skeleton art defect | G4/G8: explicit ranged attack at skeleton and goblin uses ranged pose/arrow; retain melee control |
| P17 | Existing crypt content | G8: completed goblin artwork encountered through playable exploration |
| P18 | Retained party explored knowledge in discovery/validation | G3/G8: travel to remembered out-of-sight room; no hidden current-map leakage |
| P19 | Native availability, self-action and choice gesture routing | G7/G8: Action Surge once, unavailable spells do not enter fake confirmation |
| P20 | Native exact-row budget choice and bar grouping | G7/G8: one Dash verb, correct normal/restricted budget without invented Haste action |
| P21 | Native/public identity retention and existing combat log | G7/G8: known opportunity-death turn remains named with correct ancestry |
| P22 | Authorized interactables, physical aperture picking/highlights | G3/G7: south/north doors pick and Alt-highlight in every camera |
| P23 | Disclosed support/threshold geometry and observed lighting | G3: door and its legitimate support align/light correctly, unseen room stays hidden |
| P24 | Existing transient feedback lifetime | G7: readable error expires and clears on new input/view change |
| P25 | Native roll and log serialization/math | G7/G8: actual d20 faces/modifiers copied/displayed; live RNG unchanged |
| P26 | One authorized party audience/reducer/history | G3–G8: split-room shared scene and enemy actions witnessed by either hero once |
| P27 | Native worker plus independent media readiness | G0/G2/G8: input stays responsive and total command-to-playback budgets pass separately |
| P28 | Existing gesture ownership/native generation | G3/G7/G8: no click-through, duplicate spend or stale target on replies/rotation |
| P29 | Support-layer grid composition | G3: floor < grid/ground preview < walls/props/actors at actual elevation |
| P30 | Retained controlled-actor contact and historical commit ordering | G4/G8: Haste potion replay/scene construction; informative fail-fast diagnostics |
| P31 | Native incapacitated decision-boundary handling | G8: 0 HP does not hand player an unusable decision; death saves/recovery retain native rules |

Earlier UI/environment requirements are also G8 gates: fixed Fighter/Sorcerer
launch; playable loot/trap/lever route; small party and initiative portraits;
four separate minimal icon blocks with multi-row support; explicit melee/ranged;
same-size hover choices and level icons; stable bar while log opens; shared glass
panels; slot-hover compatible equipment; bright original icons; flush-right
aligned antialiased log, working copy, recorded math, grouped movement/blood;
cursors and commit-time highlight retirement; table/wall placement and coherent
wall/door lighting. Recheck available destruction media against delivered
registrations—the historical note about seven missing wall banks is not evidence
they remain absent. List any actual missing art by exact binding and source;
the human propagates a handoff, not another-chat message.

Do not mark P05/P27 complete just because native work is off SDL, or P06 complete
because a shader is fast. Native mechanics, resource readiness and drawing each
need passing budgets. Do not move gameplay fixes into shaders to make them appear
correct in a clip.

## 12. Test and evidence plan

Read `HOW_TO_TEST.MD` before implementing. Extend existing behavior cases and
capture helpers; create only the small cross-backend fixture/harness needed to
validate this rendering boundary. Do not freeze private function calls in tests.

| Lane | Required observable result | Evidence location |
| --- | --- | --- |
| Contract/resource | Typed round-trip, exact source/data bytes, selectors cover every sampled dependency, deterministic transforms and sampled times | Existing game/export tests plus small renderer contract fixtures |
| Preparation/lifetime | Admission once, bounded bytes, no sample/draw I/O, context/reset/quit behavior, no lost historical event or active resource | Real readiness/entry-point tests, source-stage counters and generation traces |
| Desktop image/pick | Actual GL frame and matching hits for the composition/material/geometry matrices, plus corrected user-reported cases | Explicit GL test lane; private images/error maps with catalog/source hashes |
| Shader portability | Same GLSL bodies and fixtures on desktop GL and minimal WebGL 2; capability/format differences explicit | Private harness receipt, no new browser game |
| Native/controls | Existing rule/disclosure/log/input behavior, real SDL gestures and command costs | Parent engine/game tests and the actual crypt journey |
| Real performance | All parent budgets, separated CPU/native/read/decode/upload/GPU/present; no mid-effect misses | Native Windows live trace and short gameplay capture, WSL comparison second |
| Architecture/removal | Static DAG, no native import of rendering/worker objects, no late imports/reflection or unused parallel renderer | Existing architecture/typing lane and reviewed removal inventory |

Pure/default tests must not require a graphics context. GL pixel tests need a
declared environment; an absent context is reported as missing verification,
not counted as a successful rendering test. The real Windows lane is mandatory
for acceptance. Software GL may validate pixels, never the hardware FPS target.

After each family port, record all affected catalog identities and the cases
covering distinct operators/registrations/blends. Existing authored review cases
cover the full implemented spell/action catalog; automate coverage, then visually
inspect representative combinations and **every reported defect**. A single
Fireball result cannot certify all registered media; equally, do not ask the
human to watch another 298 unindexed clips to discover coverage gaps.

Use `.runtime/playtest-recovery-20261006/gpu-migration/` for run manifests,
images/clips, traces and bulky results. Commit only small plans, source contracts,
fixtures and concise receipts; keep binary art/GiB prepared planes/log dumps out
of public Git. Each run names source/diff, art release, shader/catalog version,
environment/hardware, resolution, camera and cold/warm state.

## 13. Performance and final acceptance

Keep one exact source/environment identity per run. Report preparation read,
decode, upload and compile times; working-set bytes; per-frame CPU issue time,
GPU time and present/wait; source-read/decode/upload counters during steady play.
Read GPU timer queries only after completion; do not serialize every frame with
`finish()` and call that normal play. A diagnostic synchronized measurement must
say so. Test capability/version and actual hardware renderer, not only GL success.

Image/selection evidence: all four cameras, fractional pan, supported zooms,
eight-direction bank plus residual alignment, crop/pivot seams, source alpha,
palette swap and owner/data byte order; masks/clearance and material families
listed above. Compare CPU/GPU error maps with declared per-operation rounding
tolerances and visually inspect actual critical frames.
Numerical color tolerances cannot excuse changed owner IDs, picks, band
membership, disclosure or lifecycle timing. Portable records contain extracted
geometry inputs, not SurfaceVolume/AreaMedia/DrawCommand objects or imports.

Performance acceptance remains the parent plan's real Windows 2560×1440 full
crypt journey, first/repeated spells, post-combat blood/death, panels/scrolling,
100 operations/15 minutes and native-engine timing. Repeat representative cases
at 1920×1080 and 1280×720 and then WSL. No 4K, reduced quality, absent particles,
fixed-delta recordings or empty-room averages as substitutes.

Retain the parent's numerical budgets without relaxation: frame work p95 ≤16.7 ms
and p99 ≤25 ms, no reproducible >50 ms stable frame; input acknowledgement p95
≤50 ms/max100 ms; first-use preparation target ≤250 ms after native reply; total
warm movement/door/attack p95 ≤250 ms/max500 ms and Fireball p95 ≤1 s/max2 s.
Warm first window/playable ≤2/5 s; cold ≤5/10 s. Native operation/capture budgets,
preview latency and 15-minute/100-operation stability also remain binding.
All are targets, not achieved results. Include first and repeated effects,
four-camera changes during playback, UI/log/inventory and post-combat aftermath.

Performance reporting must include maximum individual upload/allocation call,
queue/deadline misses, actual displayed-frame intervals, all resource categories
and long-session eviction/reload behavior. A small average/p95 with a repeated
65 ms upload remains a failed first-use/interaction experience. Attribute stalls
to preparation, Python work, driver synchronization or presentation before
changing the design; do not reduce visible content to hide them.

G8 finishes only with a playable crypt launch, all P01–P31 evidence, retained UI
requirements checked, complete migrated-family inventory, no obsolete production
dispatch/cache chain and both independent **implementation** approvals. A genuine
unavailable asset dependency may be reported precisely, but is not called fixed.

## 14. Review status and next implementation step

The earlier reviews approved feasibility only. This expanded plan requires fresh
anti-slop/performance and anti-OOP/ECS/causality plan review; the receipt records
their exact verdicts and any amendments. Approval of this document is separate
from G0's measured engineering decisions and from final implementation approval.

Next renderer work is G0's complete ordering, picking and resource-deadline proofs,
then G1–G8 in dependency order. The parent native/input recovery is still active;
the addendum is not a reason to abandon those fixes or declare the app smooth.

# Thorns contact source/ECS review — October 4

Structural, causal and source-palette review approves the corrected parent implementation. Final visual-gallery acceptance remains separate; this receipt does not self-approve this reviewer's source intake or shared sampler changes, which require parent review.

Reviewed the original accepted ThornsModules.gd, compiled ss_vines material and donor Start tracks against `game/thorns_surface.py`, its closed authored schema, assembly selection and existing spatial contact forwarding. Exact point-in-time files/hashes are in `wind-joined-20261004/thorns-review-snapshot.json`.

Two concrete source defects were found and corrected before this decision:

1. Whole-cell module shifts disagreed with existing canonical section centers on diagonals. Final shifts use length/count spacing, translating each unscaled donor to the same center used by `module_is_received`. Source interior variation still leaves endpoints unchanged. Opaque observed-shell admission is retained; filtering raw surface points by ground-cell visibility would incorrectly erase a legitimately received opaque wall face.
2. Choosing the nearest raw triangle before dissolve/scissor could let a discarded near vine hide a surviving farther vine. Final source UV predicate runs through the shared sampler's optional pre-depth admission. It implements the original noise/UV dissolve threshold and final alpha-scissor gate. The shared four-camera regression checks both triangle orders and exposes the farther survivor.

The final nearby-body filter uses the established lifted body elevation, restricts the original ground contact to nearby received actors and takes the source's nearest sixteen. Exact dated positive damage from the existing owner lifetime drives the local pulse; current received body contacts drive quiet movement. Sight loss removes that actor from the contact input. There is no second mechanical contact, repeated damage rule, private event queue or source-name dispatch. Original source fields remain passive typed records and pure array functions; import direction remains downward through neutral geometry, authored data and the existing sampler.

Material inputs retain the original raw mesh/normals/UV, per-module variation, native child/root transforms, evaluated Start scale/dissolve, source fixed vertex equations and lighting/palette values. Source palette registration uses two authored pixels times camera zoom, clamped at the screen sampling limit. The explicit equations and registration were reviewed; this is not a claim of bit-identical Godot whole-frame transparency, lighting or postprocessing in arbitrary world scenes.

Fresh combined source/behavior checks passed 21 cases: actual four-camera Thorns end-turn local pulls and cleanup, Wind owner/lift/lifetime behavior, and shared nearer/farther/cutout sampling. Separate shared sampler/Finger checks passed 19; the default scalar comparison remains exact in all 56 cases. These numerical checks support the integration boundary, not approval of the entire spell plan. Earlier failures and correction details remain preserved.

## Later source-palette correction

The parent identified that the actual Thorns recorder uses its CIE76 screen-grid preserve-alpha shader with color_boost1.12. Its coefficients/D65 conversion were checked against that original shader. Unlike Wind/Force's explicit nearest-RGB overrides, Thorns also multiplies unsnapped alpha by smoothstep(0,.1,max(snapped.rgb)) and clears results <=.01. These policies remain explicit per source. The actual palette shader, authoring capture adapter and representative source capture metadata are now preserved with the original intake.

Final independent numerical review passed 61 cases against a scalar implementation of the literal original Godot CIE76, boost and energy-alpha equations, plus 20 byte-identical default-RGB comparisons across sampling scales. Fresh Thorns contact/lifetime tests passed all four cases; scoped source typing has zero errors. An earlier rerun had four setup errors while a concurrent Force binding was incomplete; that log is retained, and the coherent rerun passed without weakening the loader. This closes the bounded source-palette correction, not whole-scene Godot framebuffer equivalence or whole-plan acceptance.

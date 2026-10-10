# Gameplay Regression Work Packet 019 — Execution-Owner Wrapper

Date: 2026-08-11

Status: PROPOSED — fresh Plan Gate A required

## 1. Outcome and immutable scope

This packet governs exactly one invocation of the already approved WP-019
stdin-only census literal. It adds no product or Test behavior and does not
technically reopen the literal.

The immutable authorities are:

- plan path:
  `/mnt/c/Users/tommaso/Documents/Dev/dnd_engine/agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_WORK_PACKET_019_PROCESS_CENSUS_GENERATION_PINNED_EMPTY_ARGV_REVALIDATION_2026-08-11.md`;
- plan identity: 6,033 lines / 220,198 bytes /
  `8368ff2a959c881713ec2fbb463fa12587262781c7e77a4f6fba76c7c1e5dc51`;
- embedded literal: exact plan lines 1158–5935 inclusive, 4,778 lines /
  162,847 bytes /
  `bc76a559593b567440f4c47353f67ffb528facc7acb42ae77307923cf84ce517`;
- literal final record: `# __WP019_LITERAL_END__` followed by one LF;
- protocol-static closure: Coordinator task
  `019feae2-51ed-7dc3-be98-4445f279425d`, turn
  `019ff08e-308b-7271-a66f-a5deaa30daa3`, unconditional R1–R4 4/4.

The approved plan and literal remain byte-read-only. No standalone literal,
temporary file, extracted artifact, transformed copy, pipeline, command
substitution, network action, service, product/Test edit, package edit,
dependency action, cleanup, or retry is permitted. The sole new program text
is the exact noninteractive byte collector in Section 4; its equivalence to
the frozen stdin boundary is the specific subject of this fresh Gate A.

The failed wrapper identity 193 lines / 9,131 bytes /
`4485e412565afbd6b8e9dd6e6beabb8147c2659a01c9dd7a30b76559cbdf58dc`
closed at one approval and three `CHANGES_REQUIRED` verdicts. It is
non-evidentiary. Its interactive Bash/Python transport is forbidden.

The noninteractive but selectively sanitized identity 303 lines / 15,565
bytes /
`9baf0824a785dbc5732305be2c17471b1fe39d00bd38eeaafdb66c4f83715c6f`
closed with no approval, three `CHANGES_REQUIRED` verdicts, and one stopped
review. It is non-evidentiary. Inherited environment entries, imported Bash
functions, PATH resolution, current-directory Python modules, and site hooks
are forbidden by this identity.

The environment-hermetic but return-unbounded identity 314 lines / 16,157
bytes /
`a6f7e0e4c9e4159942ce675191351940441a1fcc5a6587fb9ffaa632f1ce93bb`
closed with three approvals and one `CHANGES_REQUIRED` verdict. It is
non-evidentiary. An indefinite wait without a deterministic blocker receipt
is forbidden by this identity.

The timed but unbracketed-generation identity 354 lines / 18,838 bytes /
`7579258f2041dfe2ea5423a19a444811ac8676cee55ae0d0bbdcdf3581e297be`
closed with three approvals and one `CHANGES_REQUIRED` verdict. It is
non-evidentiary. A live receipt that can combine fields from different process
generations is forbidden by this identity.

The individually bracketed but pair-open identity 382 lines / 20,554 bytes /
`a6b2955c37195ead227cf4a6586e156ddda5c5d44c41c61fd9c6049331b3ef56`
closed with three approvals and one `CHANGES_REQUIRED` verdict. It is
non-evidentiary. Independently sound wrapper and child receipts that do not
prove the pair coexisted are forbidden by this identity.

WP-020 remains deferred at its missing public same-response-to-prepared-lobby
bridge. WP-017 and WP-018 remain consumed `NO RETRY`; their historical PIDs
remain unclassified.

## 2. Owners and gate sequence

Planner owns this wrapper plan only. R1–R4 independently review it. The
existing Tester continuation task
`019fec24-ec85-7eb1-9676-5bab2853a627` is the sole non-review execution owner.
Implementation and every monitor remain HOLD.

The sequence is:

1. fresh Plan Gate A R1–R4 4/4 on this exact wrapper plan;
2. Coordinator identity verification and one-shot release;
3. one Tester-owned wrapper session and exactly one census invocation;
4. immutable result delivery to Planner and Coordinator.

No review vote, failed attempt, or protocol-ready closure is itself execution
permission. Every outcome consumes the one-shot. There is no same-plan retry.

## 3. Wrapper owner and topology

The execution root is
`/mnt/c/Users/tommaso/Documents/Dev/dnd_engine`. Tester opens one fresh tool
session whose program is noninteractive
`/usr/bin/bash --noprofile --norc -c <Section-3.1-program>`. Exact
`/usr/bin/env -i LC_ALL=C.UTF-8` launches Bash from an otherwise empty
environment. No exported function, PATH, Bash startup hook, shell option,
Python control, locale variant, or other inherited entry survives. The tool
allocates a terminal only as a kernel EOF carrier; neither Bash nor Python
uses an interactive parser, prompt, Readline, or job control. Before any
marker, the wrapper sets canonical terminal EOF to control-D, disables echo,
input CR translation, software flow control, and output postprocessing, and
disables Bash trace/verbose output. Any setup output or failure stops before
invocation.

That long-lived Bash generation is the outer wrapper owner. Its actual PID,
stat field-22 starttime, PPid, process group, session, complete status
Pid/Tgid/PPid/four UIDs, raw cgroup, executable target, and complete
generation-pinned ancestry to PID 1 are recorded before any census child is
started. Every live wrapper or child receipt uses the same indivisible
read-only bracket: raw `/proc/<pid>/stat` before; all associated status,
cgroup, executable, and ancestry reads; then raw `/proc/<pid>/stat` after.
The two target stat records must have identical PID, field-22 starttime,
field-4 PPid, field-5 process group, field-6 session, and field-3 state. That
state must be exactly one of `R`, `S`, `D`, `T`, `t`, `K`, `W`, `P`, or `I`;
`Z`, `X`, `x`, an unknown value, disappearance, parse failure, or any state
change fails closed. Status identity fields must agree with the bracketed stat
fields; cgroup, executable, and ancestry must match the receipt's expected
baseline. Changing accounting fields elsewhere in raw stat does not invalidate
the bracket.

The wrapper obtains its PID from `BASHPID`, reads its own stat with Bash
redirection/read builtins, parses field 22 from the suffix after the closing
`)`, and prints exact owner ready marker containing canonical decimal
PID/starttime. The independent preflight must match both values and all
remaining owner receipts inside that bracket.

No equality such as PID=PGID=SID is assumed. The observed values are the
authority. A second complete bracket must prove the same owner generation,
identity, cgroup, executable, process group, session, state, and complete
ancestry immediately before invocation.

The wrapper consumes exact line `__WP019_OWNER_RELEASE__` before invocation.
It then has exactly one foreground child. Exact `/usr/bin/env -i` starts that
child from the Section-4.1 allowlist and exec-replaces the same child
generation with exact `/usr/bin/python3`. Python isolated/no-site flags prevent
environment, current-directory, user-site, global-site, `sitecustomize`, or
`usercustomize` substitution. The child runs the exact noninteractive
collector in Section 4. There is no background job, second child, prompt,
Readline path, service, browser, or concurrent inspector while the literal
executes before the Section-4.2 external deadline. The sole post-deadline
exception is the exact generation-specific, read-only blocker inspection in
Section 5. The completed preflight-only `/usr/bin/stty` process is absent
before owner capture and is not part of the invocation topology.

While the collector is blocked in `sys.stdin.buffer.read()` and before
terminal EOF, a completed read-only inspection records the wrapper's exact
direct child PID, starttime, PPid, process group, session, status identity,
cgroup, executable, and ancestry. It must show exactly one direct child and
the recorded wrapper as its parent/ancestor. Both the child receipt and the
simultaneous live-wrapper receipt use the complete stat-before/stat-after
bracket above. That inspector must exit before EOF, so it cannot overlap
literal compilation or live enumeration.

Any missing, reused, torn, contradictory, changing, state-changing,
incomplete, extra-child, or non-PID-1-reaching receipt fails closed before
behavioral acceptance.

### 3.1 Exact wrapper program

The outer launch argv is exactly this sequence, with the final placeholder
replaced by the literal code-block bytes below as one argument:

```text
["/usr/bin/env","-i","LC_ALL=C.UTF-8","/usr/bin/bash","--noprofile","--norc","-c","<Section-3.1-program-bytes>"]
```

The Bash `-c` argument is exactly the bytes below, excluding the code fences,
with LF line endings. No line is added, removed, substituted, or sourced:

```bash
set +x +v
set -f
PS1=
PS2=
PROMPT_COMMAND=
/usr/bin/stty -echo -opost -icrnl -inlcr -igncr -ixon -ixoff icanon eof '^D' || exit 69
owner_pid=$BASHPID
IFS= read -r stat_line < "/proc/$owner_pid/stat" || exit 69
stat_tail=${stat_line##*) }
set -- $stat_tail
owner_starttime=${20}
case "$owner_pid:$owner_starttime" in
  *[!0-9:]*|0:*|*:0) exit 69 ;;
esac
printf '__WP019_OWNER_READY__:%s:%s\n' "$owner_pid" "$owner_starttime"
IFS= read -r gate || exit 71
[ "$gate" = "__WP019_OWNER_RELEASE__" ] || exit 71
collector="import hashlib,sys;s=sys.stdin.buffer.read();(len(s)==162847 and hashlib.sha256(s).hexdigest()=='bc76a559593b567440f4c47353f67ffb528facc7acb42ae77307923cf84ce517') or sys.exit(70);g={'__name__':'__main__','__file__':'<stdin>'};exec(compile(s,'<stdin>','exec'),g,g)"
printf '__WP019_CENSUS_BEGIN__\n'
/usr/bin/env -i "LC_ALL=C.UTF-8" "NEURODRAGON_CENSUS_OUTER_PID=$owner_pid" "NEURODRAGON_CENSUS_OUTER_STARTTIME=$owner_starttime" /usr/bin/python3 -I -S -c "$collector"
child_status=$?
printf '__WP019_CENSUS_END__:%s\n' "$child_status"
printf '__WP019_OWNER_POSTWAIT__\n'
IFS= read -r gate || exit 72
[ "$gate" = "__WP019_OWNER_EXIT__" ] || exit 72
exit "$child_status"
```

The outer launch's final arguments are `/usr/bin/bash`, `--noprofile`,
`--norc`, `-c`, and that exact program as one argument. `/usr/bin/env -i`
exec-replaces itself with Bash; it is not a surviving wrapper generation.
The wrapper program contains no pipeline, command substitution, here-document,
temporary path, loop, background operator, signal, or retry.

## 4. Exact invocation and stdin transport

### 4.1 Freshly gated equivalent argv boundary

The frozen five-element form used `python3 -`. On a terminal that form makes
Python interactive, so it cannot provide a deferred compile-after-EOF program
or a prompt-free receipt. This wrapper therefore proposes one exact
ten-element hermetic equivalent boundary for this fresh technical gate:

```text
["/usr/bin/env","-i","LC_ALL=C.UTF-8","NEURODRAGON_CENSUS_OUTER_PID={recorded_outer_pid_decimal}","NEURODRAGON_CENSUS_OUTER_STARTTIME={recorded_outer_starttime_decimal}","/usr/bin/python3","-I","-S","-c","import hashlib,sys;s=sys.stdin.buffer.read();(len(s)==162847 and hashlib.sha256(s).hexdigest()=='bc76a559593b567440f4c47353f67ffb528facc7acb42ae77307923cf84ce517') or sys.exit(70);g={'__name__':'__main__','__file__':'<stdin>'};exec(compile(s,'<stdin>','exec'),g,g)"]
```

The brace values are replaced only by the canonical positive decimal PID and
starttime already recorded for the live wrapper owner. No fallback, inferred
parent, alternate environment key, extra argument, alternate collector, or
alternate interpreter is allowed. The Python exec environment contains
exactly `LC_ALL=C.UTF-8` and the two canonical outer-owner keys. Absolute
paths plus `-I -S` make environment, PATH, imported-function, current-directory
module, user/global site, and startup-hook substitution impossible.

The collector is noninteractive even though its input descriptor is a
terminal. It performs one raw read to terminal EOF, validates exact byte count
and SHA-256 without changing `s`, compiles those same bytes once as filename
`<stdin>` in `exec` mode, and executes that code once with `__name__` and
`__file__` matching direct stdin program semantics. It emits no success byte.
Byte mismatch exits 70 before compile. Compile/runtime stderr or any other
collector fault is retained and non-green. The approved literal does not read
`sys.argv`, `sys.path`, `__name__`, `__file__`, `__spec__`, or `__package__`;
its final `sys.exit` propagates unchanged through `exec`.

This collector is not a second census or substitute implementation. It
contains no process enumeration, classification, mutation, file operation,
network operation, retry, or cleanup. Gate A must explicitly approve or reject
this equivalence; the prior protocol-static vote does not approve it.

### 4.2 Direct EOF-terminated bytes and transcript

Tester supplies the exact approved literal bytes directly through the tool
session's terminal stdin while the collector owns that stream. Ordinary
bounded transport chunks must concatenate to plan lines 1158–5935 exactly
once, in order, without gap, overlap, normalization, CR, added byte, omitted
byte, or re-encoding. The longest frozen source line is 128 bytes, below the
canonical terminal line bound. The final program byte is the LF after
`# __WP019_LITERAL_END__`; one control-D then produces terminal EOF and is not
a program byte. No file, pipe, here-document, extraction command, command
substitution, socket, memory file, or transformation mediates the bytes.

The successful terminal write containing that sole control-D arms exactly one
external monotonic return deadline of 180,000 milliseconds. The immutable
tool-call receipt for that write supplies time zero; deadline expiry is time
zero plus exactly 180,000 milliseconds. This deadline belongs to the Tester
execution controller, not to Bash, `/usr/bin/env`, Python, the collector, or
the literal. It starts no process, sends no signal, changes no stdin byte, and
does not alter the wrapper program or child argv. Natural return is timely
only when the exact census-end and owner-postwait markers are received before
the deadline. There is no extension, reset, second timer, grace period, or
retry.

The wrapper emits exact line `__WP019_CENSUS_BEGIN__` before starting the child
and exact line `__WP019_CENSUS_END__:<decimal-exit>` after it returns. Between
those markers, the child must emit exactly one complete compact JSON line
matching schema `generation-pinned-empty-argv-revalidation-v1` and no other
byte. Noninteractive Bash emits no prompt, and `python3 -c` emits no banner or
prompt. Terminal echo and output processing are disabled before the begin
marker. Because the collector emits nothing on success and the frozen literal
has exactly one stdout print, any additional inter-marker byte is retained as
stderr/transport contamination and makes the result non-green. Tool warning
or truncation also fails closed.

The raw transcript, exact JSON bytes, parsed JSON, empty-stderr receipt, child
exit, marker count, argv, environment values, literal identity, and invocation
count are retained. Exit 0 is eligible only when the JSON has empty `errors`
and `matches`; exit 1 must correspond to a nonempty `errors` or `matches`.
Every malformed or contradictory output/exit pairing is non-green.

## 5. Natural teardown and absence proof

The literal performs no signal, mutation, cleanup, sleep, retry, network
operation, service launch, or filesystem write. The wrapper waits for the
single child to return naturally. The external 180,000-millisecond deadline
is an observation bound, never a cleanup timeout; neither wrapper nor
controller signals the child.

If the child returns naturally and the exact census-end and owner-postwait
markers arrive before the deadline, read-only postflight must prove:

- the recorded child generation is absent;
- a complete bracketed live-wrapper receipt proves the wrapper has no
  children;
- the exact wrapper generation, identity, cgroup, process group, session, and
  PID-1 ancestry still match preflight;
- the invocation count is exactly one.

The wrapper next emits exact line `__WP019_OWNER_POSTWAIT__` and consumes exact
line `__WP019_OWNER_EXIT__`. Only after the postflight receipts match does
Tester send that line. The noninteractive wrapper then exits naturally with
the recorded child status. Final read-only absence proof must show the
recorded wrapper generation absent and the tool session closed. No name scan,
port scan, census, guessed PID, group signal, kill-by-name, broad cleanup, or
unrelated process claim is allowed.

If the exact return markers have not arrived by the deadline, the outcome is
immediately and irrevocably a non-green protocol blocker. Tester does not send
`__WP019_OWNER_EXIT__`. One read-only expiry inspection, limited to the two
already recorded absolute PID paths, retains the deadline timestamp and uses
exactly this pair-closing order:

1. read and retain wrapper raw `/proc/<wrapper_pid>/stat` before;
2. obtain the complete child receipt: child raw stat before; required status,
   cgroup, executable, and ancestry reads; child raw stat after;
3. while the wrapper bracket remains open, obtain wrapper status, cgroup,
   executable, ancestry, and exact raw
   `/proc/<wrapper_pid>/task/<wrapper_pid>/children`;
4. read and retain wrapper raw stat after;
5. read and retain one final child raw stat recheck.

The wrapper and complete child brackets each apply every field/state rule from
Section 3. The children receipt must parse as exactly one canonical positive
decimal PID equal to the recorded child PID. The final child stat must preserve
the child's PID, field-22 starttime, field-3 state, and field-4 PPid from both
child bracket records, and that PPid must remain the recorded wrapper PID. The
enclosed evidence must continue to match the pre-EOF four UIDs, cgroup,
executable, ancestry, process group, session, and child-to-wrapper receipts.
Only this complete matching sequence proves that the same wrapper and child
generations coexisted after the bound.

Any absence at any step, exit, reuse, mismatch, extra/missing child, state or
parent change, return race, parse failure, or incomplete/torn pair is retained
truthfully as a contradiction and remains blocked; none may be converted into
clean absence.

After that single expiry inspection Tester stops for Coordinator disposition.
Expiry never signals, terminates, cleans, repairs, retries, starts another
invocation, sends another stdin byte, extends the wait, or manufactures an
absence receipt. The tool session and any still-live owned generations remain
untouched. Likewise, if the wrapper or child generation changes, output is
incomplete, or normal shell exit/absence cannot be proved on the timely-return
path, the result is blocked and non-green without signal or cleanup.

No evidence root exists. The immutable tool transcript and governance receipt
are the retained evidence.

## 6. Acceptance and result boundary

This packet can establish only one of:

- clean census: exit 0 with coherent empty errors/matches and complete owner,
  invocation, output, and natural-absence receipts;
- evidenced non-green census: exit 1 with coherent retained errors/matches
  and complete natural-absence receipts;
- protocol/ownership/teardown blocker: deadline expiry or any other outcome.

It cannot classify historical PIDs, make WP-018 green, approve product
behavior, waive empty argv, authorize cleanup, or release WP-020. No result
permits a second invocation.

## 7. Mandatory Plan Gate A questions

1. Are the approved plan/literal identities and prior 4/4 closure exact?
2. Is Tester the sole appropriate non-review execution owner?
3. Is every live wrapper/child generation receipt bracketed by raw stat before
   and after its associated identity/cgroup/executable/ancestry reads, with
   stable generation fields and acceptable unchanged state?
4. Is the topology exactly one noninteractive stable wrapper plus one
   foreground env/Python child, with no concurrent inspector during compile or
   enumeration?
5. Does the exact ten-element hermetic collector argv provide a technically
   equivalent boundary: clean environment, absolute executables, isolated
   no-site Python, raw EOF read, exact length/SHA validation, unchanged
   one-time compile/exec, no prompt, and unchanged literal exit semantics?
6. Are the exact 162,847 bytes delivered directly once through terminal EOF
   without a file, pipe, here-document, extraction, transformation,
   normalization, gap, or overlap?
7. Do the noninteractive transport, terminal settings, transcript markers,
   and one-JSON-line rule retain stdout, stderr, exit, warning/truncation, and
   invocation-count truthfully?
8. Is exit 0 limited to empty errors/matches and complete receipts?
9. Does the exact external 180,000-millisecond deadline make natural return
   finite while leaving natural child return followed by exact child/wrapper
   absence as the only clean teardown path?
10. On expiry, does one exact-generation read-only blocker receipt retain the
    still-live wrapper/child truth through the exact wrapper-before, complete
    child bracket, wrapper evidence/children, wrapper-after, and final-child
    sequence, with any survivor, reuse, state/parent change, torn pair,
    contradiction, race, signal need, or incomplete receipt failing closed
    without cleanup, termination, extension, or retry?
11. Do the approved WP-019 bytes, WP-017/WP-018 `NO RETRY`, and deferred
    WP-020 remain unchanged?
12. Is there any concrete false-green, ownership, safety, output, teardown,
    scope, or human-decision blocker?

Approval:

`APPROVE_WORK_PACKET_019_EXECUTION_OWNER_WRAPPER_PLAN_GATE_A`

Rejection:

`CHANGES_REQUIRED`

Approval authorizes no invocation until separate Coordinator verification and
one-shot release.

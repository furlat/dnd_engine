"use strict";

// A static review surface over one immutable generated run. It neither runs
// mechanics nor resamples animation: the video and trace are the evidence.
const ui = Object.fromEntries(["run-label", "run-details", "search", "verdict-filter", "checks-filter",
  "tags", "speed", "counts", "export", "message", "empty", "gallery"].map(id => [id, document.getElementById(id)]));
const cards = new Map();
const activeTags = new Set();
let manifest;
let storageKey;
let storageWarning = false;
let exporting = false;
let state = {reviews: {}, selected: [], speed: 1};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function button(text, action, className = "") {
  const node = element("button", className, text);
  node.type = "button";
  node.addEventListener("click", action);
  return node;
}

function message(text, error = false) {
  ui.message.hidden = !text;
  ui.message.textContent = text;
  ui.message.classList.toggle("error", error);
}

function localURL(path) {
  if (typeof path !== "string" || !path.trim()) throw new Error("Missing local artifact path");
  const url = new URL(path, location.href);
  if (url.origin !== location.origin || !["http:", "https:"].includes(url.protocol)) {
    throw new Error(`Artifact is not on this local report server: ${path}`);
  }
  return url.href;
}

async function readJSON(path) {
  const response = await fetch(localURL(path), {cache: "no-store"});
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

function review(id) {
  return state.reviews[id] || {verdict: "unreviewed", at_ms: null, notes: ""};
}

function save() {
  try { localStorage.setItem(storageKey, JSON.stringify(state)); }
  catch {
    if (!storageWarning) message("Browser storage is unavailable. Reviews remain on this page; export them before closing it.", true);
    storageWarning = true;
  }
}

function setReview(id, fields) {
  state.reviews[id] = {...review(id), ...fields};
  save();
  refreshCard(id);
  if (fields.verdict) {
    // Keep the case visible while the reviewer writes the note after marking
    // an issue, even when the previous review filter would exclude it.
    if (ui["verdict-filter"].value !== "all" && ui["verdict-filter"].value !== fields.verdict) {
      ui["verdict-filter"].value = "all";
    }
    filterCards();
  } else counts();
}

function select(id, selected) {
  state.selected = selected ? [...new Set([...state.selected, id])] : state.selected.filter(value => value !== id);
  cards.get(id).selection.checked = selected;
  save();
  counts();
}

function counts() {
  if (!manifest) return;
  const visible = [...cards.values()].filter(card => !card.node.hidden).length;
  const issues = manifest.cases.filter(row => review(row.id).verdict === "issue").length;
  const approved = manifest.cases.filter(row => review(row.id).verdict === "approved").length;
  const hidden = state.selected.filter(id => cards.get(id).node.hidden).length;
  ui.counts.textContent = `${visible} / ${cards.size} visible · ${issues} issues · ${approved} approved · ${state.selected.length} selected${hidden ? ` (${hidden} hidden)` : ""}`;
  ui.export.disabled = exporting || !state.selected.length;
  ui.empty.hidden = visible !== 0;
}

function filterCards() {
  const query = ui.search.value.trim().toLowerCase();
  for (const [id, card] of cards) {
    const row = card.record;
    const visible = (!query || [row.id, row.title, row.description, ...row.tags].join(" ").toLowerCase().includes(query))
      && [...activeTags].every(tag => row.tags.includes(tag))
      && (ui["verdict-filter"].value === "all" || review(id).verdict === ui["verdict-filter"].value)
      && (ui["checks-filter"].value === "all" || (ui["checks-filter"].value === "gaps" ? row.gaps.length > 0 : row.status === ui["checks-filter"].value));
    card.node.hidden = !visible;
    if (!visible && card.video) card.video.pause();
  }
  counts();
}

function refreshCard(id) {
  const card = cards.get(id);
  const current = review(id);
  card.node.dataset.verdict = current.verdict;
  card.issue.setAttribute("aria-pressed", String(current.verdict === "issue"));
  card.approve.setAttribute("aria-pressed", String(current.verdict === "approved"));
  card.reviewState.textContent = {unreviewed: "Unreviewed", issue: "Issue marked", approved: "Approved"}[current.verdict];
  card.pin.value = current.at_ms === null ? "" : (current.at_ms / 1000).toFixed(3);
  card.go.disabled = current.at_ms === null || !card.video;
  card.clearPin.disabled = current.at_ms === null;
}

function seek(card, seconds) {
  if (!card.video || card.video.readyState === 0) return;
  card.video.pause();
  const duration = Number.isFinite(card.video.duration) ? card.video.duration : card.record.duration_ms / 1000;
  card.video.currentTime = Math.max(0, Math.min(seconds, duration));
}

function pinNow(id) {
  const card = cards.get(id);
  if (!card.video) return;
  card.video.pause();
  setReview(id, {at_ms: card.video.currentTime * 1000});
}

function makeCard(row) {
  const node = element("article", "card");
  node.dataset.caseId = row.id;
  const header = element("div", "card-header");
  const heading = element("div", "card-heading");
  const choiceLabel = element("label", "select-case");
  const selection = element("input");
  selection.type = "checkbox";
  selection.setAttribute("aria-label", `Select ${row.title} for export`);
  selection.checked = state.selected.includes(row.id);
  selection.addEventListener("change", () => select(row.id, selection.checked));
  choiceLabel.append(selection);
  heading.append(choiceLabel, element("h2", "", row.title),
    element("span", `check-status ${row.status === "failed" ? "failed" : ""}`, row.status === "passed" ? "Checks pass" : "Checks fail"));
  header.append(heading, element("p", "case-id", row.id));
  const tags = element("div", "case-tags");
  tags.append(...row.tags.map(tag => element("span", "tag", tag)));
  header.append(tags, element("p", "description", row.description));
  const media = element("div", "video-wrap");
  let video = null;
  const mediaError = element("p", "media-error");
  mediaError.hidden = true;
  if (row.video) {
    video = element("video");
    video.controls = video.muted = video.loop = video.playsInline = true;
    video.preload = "metadata";
    video.src = localURL(row.video);
    video.setAttribute("aria-label", row.title);
    video.style.setProperty("--video-ratio", `${manifest.run.width}/${manifest.run.height}`);
    if (row.poster) video.poster = localURL(row.poster);
    video.playbackRate = state.speed;
    video.addEventListener("error", () => {
      mediaError.hidden = false;
      mediaError.textContent = "Video could not load. The case and its trace remain available for review/export.";
    });
    media.append(video);
  } else media.append(element("div", "no-video", "No video was generated. Review the failure and export its trace."));
  const body = element("div", "card-body");
  const time = element("div", "time-row");
  const playhead = element("span", "playhead", `0.000s / ${(row.duration_ms / 1000).toFixed(3)}s · ${row.frame_count} frames`);
  const back = button("−1 frame", () => seek(cards.get(row.id), video.currentTime - 1 / manifest.run.fps));
  const forward = button("+1 frame", () => seek(cards.get(row.id), video.currentTime + 1 / manifest.run.fps));
  const pinButton = button("Pin current", () => pinNow(row.id));
  for (const control of [back, forward, pinButton]) control.disabled = !video;
  if (video) video.addEventListener("timeupdate", () => {
    playhead.textContent = `${video.currentTime.toFixed(3)}s / ${(row.duration_ms / 1000).toFixed(3)}s · frame ${Math.floor(video.currentTime * manifest.run.fps)}`;
  });
  time.append(playhead, back, forward, pinButton);
  const verdict = element("div", "review-row");
  const issue = button("Mark issue", () => {
    if (video) video.pause();
    select(row.id, true);
    setReview(row.id, {verdict: "issue", ...(video ? {at_ms: video.currentTime * 1000} : {})});
    notes.focus();
  }, "issue");
  const approve = button("Approve", () => setReview(row.id, {verdict: "approved"}), "approve");
  const reset = button("Unreviewed", () => setReview(row.id, {verdict: "unreviewed"}), "quiet");
  const reviewState = element("span", "review-state");
  verdict.append(issue, approve, reset, reviewState);
  const pinRow = element("div", "pin-row");
  const pinLabel = element("label", "", "Pinned time (seconds)");
  const pin = element("input");
  pin.type = "number";
  pin.min = "0";
  pin.step = "0.001";
  pin.max = String(row.duration_ms / 1000);
  pin.placeholder = "No moment pinned";
  pin.addEventListener("change", () => {
    if (!pin.checkValidity()) { pin.reportValidity(); return; }
    setReview(row.id, {at_ms: pin.value === "" ? null : Math.round(Number(pin.value) * 1000)});
  });
  pinLabel.append(pin);
  const go = button("Go to pin", () => seek(cards.get(row.id), review(row.id).at_ms / 1000));
  const clearPin = button("Clear pin", () => setReview(row.id, {at_ms: null}), "quiet");
  pinRow.append(pinLabel, go, clearPin);
  const notesLabel = element("label", "notes", "Review note");
  const notes = element("textarea");
  notes.placeholder = "Describe what should change at this moment…";
  notes.value = review(row.id).notes;
  notes.addEventListener("input", () => setReview(row.id, {notes: notes.value}));
  notesLabel.append(notes);
  const footer = element("div", "case-footer");
  if (row.trace) {
    const trace = element("a", "", "Open raw trace ↗");
    trace.href = localURL(row.trace);
    trace.target = "_blank";
    trace.rel = "noopener";
    footer.append(trace);
  } else footer.append(element("span", "media-error", "Trace path missing"));
  footer.append(button("Export this case", () => exportCases([row.id])));
  const evidence = element("details", "evidence");
  evidence.open = row.status === "failed";
  evidence.append(element("summary", "", `${row.checks.length} checks · ${row.gaps.length} presentation gaps`));
  const checks = element("ul");
  checks.append(...row.checks.map(check => element("li", check.passed ? "" : "failed",
    `${check.passed ? "✓" : "✕"} ${check.name}${check.detail ? ` — ${check.detail}` : ""}`)));
  checks.append(...row.gaps.map(gap => element("li", "gap", `Gap: ${gap}`)));
  evidence.append(checks);
  if (row.error) evidence.append(element("pre", "", row.error));
  body.append(time, verdict, pinRow, notesLabel, footer, evidence);
  node.append(header, media, mediaError, body);
  cards.set(row.id, {record: row, node, video, selection, issue, approve, reviewState, pin, go, clearPin});
  refreshCard(row.id);
  return node;
}

async function playback(action) {
  const videos = [...cards.values()].filter(card => !card.node.hidden && card.video);
  const results = await Promise.allSettled(videos.map(async card => {
    const video = card.video;
    if (action === "pause") { video.pause(); return; }
    if (action === "restart") { video.pause(); video.currentTime = 0; }
    try { await video.play(); } catch (error) { throw new Error(`${card.record.id}: ${error.message}`); }
  }));
  const failures = results.filter(result => result.status === "rejected").map(result => result.reason.message);
  if (failures.length) message(`Some videos could not play:\n${failures.join("\n")}`, true);
}

async function exportCases(ids) {
  if (exporting || !ids.length) return;
  exporting = true;
  counts();
  const selected = ids.map(id => ({case: cards.get(id).record, review: {...review(id)}}));
  message(`Loading complete traces for ${selected.length} selected case${selected.length === 1 ? "" : "s"}…`);
  try {
    const results = await Promise.allSettled(selected.map(async entry => {
      const trace = await readJSON(entry.case.trace);
      if (trace?.run?.id !== manifest.run.id || trace?.run?.source_hash !== manifest.run.source_hash
          || trace?.case?.id !== entry.case.id) {
        throw new Error("Trace identity differs from the reviewed run/case. Reload the correct immutable run.");
      }
      // MP4 timestamps have microsecond precision; retain the pinned time and
      // identify its preceding source frame without integer-ms rounding loss.
      const frames = Array.isArray(trace.frames) ? trace.frames : [];
      const selectedFrame = entry.review.at_ms === null ? null : frames.reduce((latest, frame) =>
        Number.isFinite(frame.video_ms) && frame.video_ms <= entry.review.at_ms + .001
          && (latest === null || frame.video_ms > latest.video_ms) ? frame : latest, null);
      return {...entry, review: {...entry.review, selected_frame_index: selectedFrame?.index ?? null}, trace};
    }));
    const failures = results.flatMap((result, index) => result.status === "rejected" ? [`${selected[index].case.id}: ${result.reason.message}`] : []);
    if (failures.length) throw new Error(`Nothing was exported. Complete traces could not be loaded:\n${failures.join("\n")}`);
    const selections = results.map(result => result.value);
    const blob = new Blob([JSON.stringify({schema_version: 1, kind: "dnd-animation-review", run: manifest.run, selections}, null, 2)], {type: "application/json"});
    const url = URL.createObjectURL(blob);
    const link = element("a");
    link.href = url;
    link.download = `animation-review-${String(manifest.run.id).replace(/[^a-zA-Z0-9._-]/g, "-")}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    message(`Exported ${selections.length} complete case${selections.length === 1 ? "" : "s"}, with pinned times, notes and run identity.`);
  } catch (error) { message(error.message, true); }
  finally { exporting = false; counts(); }
}

async function initialize() {
  try {
    manifest = await readJSON("manifest.json");
    if (manifest.schema_version !== 1 || !manifest.run?.id || !manifest.run.source_hash || !Array.isArray(manifest.cases)
        || !(manifest.run.fps > 0) || !(manifest.run.width > 0) || !(manifest.run.height > 0)) {
      throw new Error("Unsupported or incomplete review manifest; expected schema version 1 with run/video dimensions.");
    }
    const ids = new Set();
    for (const row of manifest.cases) {
      if (!row.id || ids.has(row.id) || typeof row.title !== "string" || !Array.isArray(row.tags)
          || !Array.isArray(row.checks) || !Array.isArray(row.gaps) || !["passed", "failed"].includes(row.status)
          || !Number.isFinite(row.duration_ms) || row.duration_ms < 0 || !Number.isInteger(row.frame_count)) {
        throw new Error(`Invalid or duplicate case in the manifest: ${row.id || "(missing id)"}`);
      }
      ids.add(row.id);
    }
    storageKey = `dnd-animation-review:${manifest.run.id}:${manifest.run.created_at}:${manifest.run.source_hash}`;
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "null");
      if (saved) {
        const reviews = {};
        for (const id of ids) {
          const row = saved.reviews?.[id];
          if (row && ["issue", "approved", "unreviewed"].includes(row.verdict) && typeof row.notes === "string"
              && (row.at_ms === null || Number.isFinite(row.at_ms) && row.at_ms >= 0)) reviews[id] = row;
        }
        state = {reviews, selected: (Array.isArray(saved.selected) ? saved.selected : []).filter(id => ids.has(id)),
          speed: [.25, .5, 1, 1.5, 2].includes(saved.speed) ? saved.speed : 1};
      }
    } catch { message("Saved browser review could not be restored. The generated run is unaffected.", true); }
    ui.speed.value = String(state.speed);
    const run = manifest.run;
    if (run.layout === "four-corners-2x2") {
      document.getElementById("subtitle").textContent = "Every recording shows all four camera corners of the same sequence.";
      document.getElementById("playback-hint").textContent = "Views 0 / 1 above 2 / 3. Use video fullscreen; pin a frame and name the corner in your note. Clips loop independently.";
    }
    ui["run-label"].textContent = `${run.branch || "Unknown branch"} · ${String(run.commit || "").slice(0, 10)}${run.dirty ? " · working tree modified" : ""}\n${run.id}\n${run.fps} fps · ${run.width} × ${run.height}`;
    for (const [name, value] of Object.entries(run)) ui["run-details"].append(element("dt", "", name), element("dd", "", typeof value === "object" ? JSON.stringify(value) : String(value)));
    for (const tag of [...new Set(manifest.cases.flatMap(row => row.tags))].sort()) {
      const chip = button(tag, () => {
        if (activeTags.has(tag)) activeTags.delete(tag); else activeTags.add(tag);
        chip.setAttribute("aria-pressed", String(activeTags.has(tag)));
        filterCards();
      });
      chip.setAttribute("aria-pressed", "false");
      ui.tags.append(chip);
    }
    ui.gallery.append(...manifest.cases.map(makeCard));
    filterCards();
  } catch (error) {
    ui["run-label"].textContent = "Run unavailable";
    ui.counts.textContent = "The gallery could not load.";
    message(`Unable to open this review run. Serve its output directory over localhost.\n${error.message}`, true);
  }
}

for (const id of ["search", "verdict-filter", "checks-filter"]) ui[id].addEventListener(id === "search" ? "input" : "change", filterCards);
document.getElementById("clear-filters").addEventListener("click", () => {
  ui.search.value = "";
  ui["verdict-filter"].value = ui["checks-filter"].value = "all";
  activeTags.clear();
  for (const chip of ui.tags.children) chip.setAttribute("aria-pressed", "false");
  filterCards();
});
for (const action of ["play", "pause", "restart"]) document.getElementById(`${action}-all`).addEventListener("click", () => playback(action));
ui.speed.addEventListener("change", () => {
  state.speed = Number(ui.speed.value);
  for (const card of cards.values()) if (card.video) card.video.playbackRate = state.speed;
  save();
});
document.getElementById("select-visible").addEventListener("click", () => {
  for (const [id, card] of cards) if (!card.node.hidden) select(id, true);
});
document.getElementById("clear-selection").addEventListener("click", () => {
  for (const id of [...state.selected]) select(id, false);
});
ui.export.addEventListener("click", () => exportCases([...state.selected]));
initialize();

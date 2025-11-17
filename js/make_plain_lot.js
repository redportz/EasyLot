/* === CONFIG === */
const SLOT_W = 60;                             // drawn slot width (px)
const SLOT_H = 100;                             // drawn slot height (px)
const STATUS_POLL_MS = 7000;                   // how often to refresh colors

/* === DOM === */
const stage = document.getElementById("stage");                // <svg id="stage">
const tableBody = document.querySelector("#stallTable tbody"); // optional table
const plainMsgEl = document.getElementById("plainMsg");        // optional status text
let doneBtn = document.getElementById("btnDone");

// Optional legacy buttons (we hide them if present)
const addBtn    = document.getElementById("addBox");
const toggleBtn = document.getElementById("toggleStatus");
const deleteBtn = document.getElementById("deleteBox");

/* === LOT ID FROM URL === */
const params = new URLSearchParams(location.search);
const lotId = Number(params.get("lotId") || params.get("id"));

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

if (!lotId) {
  alert("Missing ?id= or ?lotId= in URL.");
  throw new Error("lotId missing");
}

function nextGridPos(i, { startX=80, startY=80, gapX=20, gapY=20, cols=8 } = {}) {
  const r = Math.floor(i / cols), c = i % cols;
  return {
    x: startX + c * (SLOT_W + gapX),
    y: startY + r * (SLOT_H + gapY),
  };
}

/* === STATE === */
let stalls = [];               
let selected = null;
let dragOffset = { x: 0, y: 0 };
let rotating = false;
let editing = false; 
let spotIdByNumber = new Map(); 

/* === HELPERS === */
function getMouseInSvg(e) {
  const r = stage.getBoundingClientRect();
  return { x: e.clientX - r.left, y: e.clientY - r.top };
}
function angleDeg(cx, cy, mx, my) {
  const a = Math.atan2(my - cy, mx - cx) * 180 / Math.PI;
  return (a + 360) % 360;
}
function colorFromMouse(cx, cy, mx, my) {
  const dx = mx - cx, dy = my - cy;
  const dist = Math.hypot(dx, dy);
  const hue = angleDeg(cx, cy, mx, my);
  const maxD = 250;
  const light = 65 - Math.min((dist / maxD) * 35, 35);
  return `hsl(${hue} 70% ${light}%)`;
}

function syncWithSpots(spots) {
  const spotNos = new Set(spots.map(sp => sp.spot_number));
  const statusByNo = new Map(spots.map(sp => [sp.spot_number, sp.status]));

  // A) remove boxes whose spot was deleted
  stalls = stalls.filter(s => spotNos.has(s.spot_number));

  // B) add boxes for brand-new spots (append at the end)
  const haveNo = new Set(stalls.map(s => s.spot_number));
  const newSpots = spots
    .map(sp => sp.spot_number)
    .filter(no => !haveNo.has(no))
    .sort((a,b) => a - b);

  for (const no of newSpots) {
    const pos = nextGridPos(stalls.length);   // simple append position
    stalls.push({
      spot_number: no,
      status: statusByNo.get(no) ?? "unknown",
      x: pos.x,
      y: pos.y,
      rotation: 0,
      fill: undefined,
    });
  }

  stalls.forEach(s => { s.status = statusByNo.get(s.spot_number) ?? s.status; });

  stalls.sort((a,b) => a.spot_number - b.spot_number);
}


/* === SERVER CALLS === */
async function fetchSpots(lotId) {
  const r = await fetch(`/lots/${lotId}/spots`, { cache: "no-store" });
  if (!r.ok) throw new Error(`Failed to load spots: ${r.status}`);
  return r.json(); // [{id, spot_number, status, ...}]
}
async function fetchPlainSlots(lotId) {
  const r = await fetch(`/lots/${lotId}/plain_slots`, { cache: "no-store" });
  if (!r.ok) throw new Error(`Failed to load plain slots: ${r.status}`);
  return r.json(); // [{id, spot_id, slot_number, x, y, rotation, ...}]
}

/* === INITIAL SEED (grid) WHEN NO PLAIN SLOTS EXIST === */
function seedGridFromSpots(
  spots,
  { startX = 80, startY = 80, gapX = 20, gapY = 20, cols = 8 } = {}
) {
  const out = [];
  for (let i = 0; i < spots.length; i++) {
    const sp = spots[i];
    const r = Math.floor(i / cols);
    const c = i % cols;
    const cx = startX + c * (SLOT_W + gapX);
    const cy = startY + r * (SLOT_H + gapY);
    out.push({
      spot_number: sp.spot_number,
      status: sp.status ?? "unknown",
      x: cx,
      y: cy,
      rotation: 0,
      fill: undefined,
    });
  }
  return out;
}

/* === RENDER === */
function render(lastMouse = null) {
  stage.innerHTML = "";
  stalls.forEach((stall) => {
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.classList.add("stall");
    g.dataset.spot_number = stall.spot_number;
    g.dataset.status = stall.status;
    if (selected === stall.spot_number) g.classList.add("selected");

    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    const cx = stall.x, cy = stall.y;

    rect.setAttribute("x", cx - SLOT_W / 2);
    rect.setAttribute("y", cy - SLOT_H / 2);
    rect.setAttribute("width", SLOT_W);
    rect.setAttribute("height", SLOT_H);
    rect.setAttribute("transform", `rotate(${stall.rotation},${cx},${cy})`);
    rect.setAttribute("class", "box");

    // color: live status; while dragging with Shift, show hue preview
    if (selected === stall.spot_number && lastMouse && rotating) {
      rect.setAttribute("fill", colorFromMouse(cx, cy, lastMouse.x, lastMouse.y));
    } else if (stall.fill) {
      rect.setAttribute("fill", stall.fill);
    } else if (stall.status === "full") {
      rect.setAttribute("fill", "#c0392b");
    } else if (stall.status === "empty") {
      rect.setAttribute("fill", "#27ae60");
    } else {
      rect.setAttribute("fill", "#b7b300");
    }

    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.textContent = stall.spot_number;
    text.setAttribute("x", cx);
    text.setAttribute("y", cy + 5);
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("fill", "white");
    text.setAttribute("font-size", "12");
    text.setAttribute("pointer-events", "none");

    g.appendChild(rect);
    g.appendChild(text);
    g.addEventListener("mousedown", (e) => selectStall(e, stall));
    stage.appendChild(g);
  });
  updateTable();
}

function updateTable() {
  if (!tableBody) return;
  tableBody.innerHTML = stalls
    .map(
      (s) => `
    <tr${s.spot_number === selected ? ' style="background:#223"' : ""}>
      <td>${s.spot_number}</td>
      <td>${Math.round(s.x)}</td>
      <td>${Math.round(s.y)}</td>
      <td>${Math.round(s.rotation)}</td>
      <td>${s.status}</td>
    </tr>`
    )
    .join("");
}

/* === INTERACTIONS === */
function selectStall(e, stall) {
  editing = true;
  selected = stall.spot_number;
  const m = getMouseInSvg(e);
  dragOffset.x = m.x - stall.x;
  dragOffset.y = m.y - stall.y;
  rotating = e.shiftKey;
  document.onmousemove = moveStall;
  document.onmouseup = stopDrag;
  render(m);
}
function moveStall(e) {
  const stall = stalls.find((s) => s.spot_number === selected);
  if (!stall) return;
  const m = getMouseInSvg(e);
  const cx = stall.x, cy = stall.y;

  if (rotating) {
    stall.rotation = (angleDeg(cx, cy, m.x, m.y) + 90) % 360;
    stall.fill = colorFromMouse(cx, cy, m.x, m.y); // live preview color while rotating
  } else {
    stall.x = m.x - dragOffset.x;
    stall.y = m.y - dragOffset.y;
  }
  render(m);
}
function stopDrag() {
  document.onmousemove = null;
  document.onmouseup = null;
  rotating = false;
  editing = false;
}
document.addEventListener("keydown", (e) => {
  if (e.key === "Shift") rotating = true;
});
document.addEventListener("keyup", (e) => {
  if (e.key === "Shift") rotating = false;
});

/* === SAVE === */
function buildPlainSlotsPayload() {
  const slots = stalls.map((s) => ({
    spot_id: spotIdByNumber.get(s.spot_number) ?? undefined, // backend can also use slot_number
    slot_number: s.spot_number,
    x: Number(s.x),
    y: Number(s.y),
    rotation: Number(s.rotation || 0),
  }));
  return { slots };
}
async function savePlainSlots() {
  try {
    const payload = buildPlainSlotsPayload();
    const r = await fetch(`/lots/${lotId}/plain_slots`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    const res = await r.json();
    msg(`Saved ${res.count} slots.`, "ok");
  } catch (e) {
    console.error(e);
    msg(`Save failed: ${e.message}`, "err");
  }
}

let statusRefreshInFlight = false;
let lastStatusRefresh = 0;

async function refreshStatusesOnly() {
  // don't poll while user is dragging/rotating
  if (editing) return;

  // don't poll if tab is hidden (saves a LOT of noise)
  if (document.hidden) return;

  // ensure only one refresh is running at a time
  if (statusRefreshInFlight) return;

  const now = Date.now();
  const MIN_GAP = STATUS_POLL_MS * 0.8; // allow some flexibility

  // if we got called "too soon", back off a bit plus jitter
  const elapsed = now - lastStatusRefresh;
  if (elapsed < MIN_GAP) {
    const jitter = 500 + Math.random() * 1500; // 0.5–2s jitter
    await sleep(MIN_GAP - elapsed + jitter);
  }

  statusRefreshInFlight = true;
  try {
    // extra jitter before hitting the API so many clients de-sync
    const jitterBefore = Math.random() * 2000; // 0–2s
    await sleep(jitterBefore);

    const spots = await fetchSpots(lotId);
    syncWithSpots(spots);
    render();
    lastStatusRefresh = Date.now();
  } catch (err) {
    console.error(err);
  } finally {
    statusRefreshInFlight = false;
  }
}



/* === INIT === */
async function initFromDB() {
  // 1) spots -> map id + initial statuses (no polygons used here)
  const spots = await fetchSpots(lotId);
  spotIdByNumber = new Map(spots.map((sp) => [sp.spot_number, sp.id]));

  // 2) try loading saved plain slots
  const plain = await fetchPlainSlots(lotId);

  if (plain.length) {
    // Build stalls strictly from plain slots (top-down plan)
    const statusBySpotId = new Map(spots.map((sp) => [sp.id, sp.status]));
    const statusBySlotNo = new Map(spots.map((sp) => [sp.spot_number, sp.status]));
    stalls = plain.map((p) => ({
      spot_number: p.slot_number,
      status: statusBySpotId.get(p.spot_id) ?? statusBySlotNo.get(p.slot_number) ?? "unknown",
      x: Number(p.x),
      y: Number(p.y),
      rotation: Number(p.rotation || 0),
      fill: undefined,
    }));
  } else {
    // First-time: simple grid seed (top-down)
    stalls = seedGridFromSpots(spots);
  }

  syncWithSpots(spots);

  selected = null;
  render();
}

/* === UTIL === */
function msg(text, kind = "ok") {
  if (!plainMsgEl) return;
  plainMsgEl.textContent = text;
  plainMsgEl.style.color = kind === "ok" ? "#0a0" : kind === "warn" ? "#a60" : "#c00";
}

/* === BOOT === */
(async function boot() {

  // Ensure we have a Done button
  if (!doneBtn) {
    doneBtn = document.createElement("button");
    doneBtn.id = "btnDone";
    doneBtn.textContent = "Done";
    document.body.appendChild(doneBtn);
  }
  doneBtn.addEventListener("click", savePlainSlots);

  try {
    await initFromDB();
    // Poll only for status color changes
    setInterval(refreshStatusesOnly, STATUS_POLL_MS);
    msg("Plan loaded.", "ok");
  } catch (e) {
    console.error(e);
    msg(`Init failed: ${e.message}`, "err");
  }
})();

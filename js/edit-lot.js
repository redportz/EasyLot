/* === CONFIG === */
const BACKEND = "http://127.0.0.1:5000";  // change if needed
// If you later enable auth, set TOKEN or read from localStorage.
const TOKEN = null;

// Keep these in sync with your Flask server FRAME_W/FRAME_H
const FRAME_W = 1280;
const FRAME_H = 720;

/* === DOM === */
const streamEl = document.getElementById("stream");
const canvas   = document.getElementById("lot");
const ctx      = canvas.getContext("2d");
const msg      = document.getElementById("msg");
document.getElementById("backendUrlText").textContent = BACKEND;

const btnUndoPoint = document.getElementById("btnUndoPoint");
const btnUndoPoly  = document.getElementById("btnUndoPoly");
const btnClear     = document.getElementById("btnClear");
const btnReload    = document.getElementById("btnReload");
const btnSave      = document.getElementById("btnSave");

/* === STATE === */
let polygons = [];         // [ [ [x,y],[x,y],[x,y],[x,y] ], ... ]
let draft = [];

/* === STREAM === */
function startStream() {
  // cache-bust with a timestamp so browsers don't freeze on first frame
  streamEl.src = `${BACKEND}/video_feed?ts=${Date.now()}`;
}
startStream();

/* === DRAW === */
function draw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Existing polygons
  polygons.forEach(poly => {
    ctx.fillStyle = "rgba(0, 180, 0, 0.25)";
    ctx.strokeStyle = "#22a";
    ctx.lineWidth = 2;

    ctx.beginPath();
    poly.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // corner dots
    poly.forEach(([x, y]) => {
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = "#2c2";
      ctx.fill();
    });
  });

  // Draft poly
  if (draft.length) {
    ctx.strokeStyle = "#c22";
    ctx.fillStyle = "#f55";
    ctx.beginPath();
    draft.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
    ctx.stroke();
    draft.forEach(([x, y]) => {
      ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill();
    });
  }

  // HUD
  ctx.fillStyle = "#333";
  ctx.font = "14px system-ui";
  ctx.fillText(`Polygons: ${polygons.length}   Draft: ${draft.length}/4`, 12, 20);
}

/* === EVENTS === */
canvas.addEventListener("click", (e) => {
  const rect = canvas.getBoundingClientRect();
  const x = Math.round((e.clientX - rect.left)  * (canvas.width  / rect.width));
  const y = Math.round((e.clientY - rect.top)   * (canvas.height / rect.height));

  draft.push([x, y]);
  if (draft.length === 4) {
    polygons.push(draft.slice());
    draft = [];
    setMsg("Polygon added.", "ok");
  } else {
    setMsg(`Point ${draft.length}/4`, "ok");
  }
  draw();
});

btnUndoPoint.addEventListener("click", () => {
  if (draft.length) { draft.pop(); setMsg("Removed last draft point.", "ok"); }
  else              { setMsg("No draft points.", "warn"); }
  draw();
});

btnUndoPoly.addEventListener("click", () => {
  if (polygons.length) { polygons.pop(); setMsg("Removed last polygon.", "ok"); }
  else                 { setMsg("No polygons.", "warn"); }
  draw();
});

btnClear.addEventListener("click", () => {
  polygons = []; draft = []; draw();
  setMsg("Cleared local polygons (not saved).", "ok");
});

btnReload.addEventListener("click", async () => {
  try { await loadPolygons(); setMsg(`Reloaded ${polygons.length} from server.`, "ok"); draw();}
  catch (e) { setMsg(`Reload failed: ${e.message}`, "err"); }
});

btnSave.addEventListener("click", async () => {
  try { await savePolygons(polygons); setMsg(`Saved ${polygons.length} polygons.`, "ok"); }
  catch (e) { setMsg(`Save failed: ${e.message}`, "err"); }
});

/* === API === */
async function loadPolygons() {
  const r = await fetch(`${BACKEND}/polygons`, { cache: "no-store" });
  if (!r.ok) throw new Error(`GET /polygons -> ${r.status}`);
  const j = await r.json();
  polygons = Array.isArray(j.polygons) ? j.polygons : [];
}

async function savePolygons(polys) {
  const headers = { "Content-Type": "application/json" };
  if (TOKEN) headers["X-ADMIN-TOKEN"] = TOKEN;
  const r = await fetch(`${BACKEND}/polygons`, {
    method: "POST",
    headers,
    body: JSON.stringify({ polygons: polys }),
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

/* === UTIL === */
function setMsg(text, kind="ok") {
  msg.textContent = text;
  msg.style.color = kind === "ok" ? "#0a0" : kind === "warn" ? "#a60" : "#c00";
}

/* === INIT === */
(async function init(){
  try { await loadPolygons(); setMsg(`Loaded ${polygons.length} polygons.`, "ok"); }
  catch (e) { setMsg(`Initial load failed: ${e.message}`, "err"); }
  draw();
})();
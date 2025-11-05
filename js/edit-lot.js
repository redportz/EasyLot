
/* === CONFIG === */
const BACKEND = "http://127.0.0.1:5000"; 
const DB =  "http://127.0.0.1:5001";
const params = new URLSearchParams(window.location.search);
const lotId = params.get("id");
if (!lotId) {
  alert("Missing ?id= in URL.");
  window.location.href = "/index.html";
}

// Keep these in sync with your Flask server FRAME_W/FRAME_H
const FRAME_W = 1280;
const FRAME_H = 720;

/* === DOM === */
const streamEl = document.getElementById("stream");
const canvas   = document.getElementById("lot");
const ctx      = canvas.getContext("2d");
const msg      = document.getElementById("msg");

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
  streamEl.src = `${BACKEND}/video_feed/${lotId}?ts=${Date.now()}`;
}
startStream();

/* === DRAW === */
function draw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  polygons.forEach((poly, i) => {
    if (!Array.isArray(poly) || poly.length === 0) return;

    const spot = (window._spots || [])[i];
    const status = spot?.status || "unknown";
    const spotNum = spot?.spot_number ?? i + 1;

    // === Color by status ===
    switch (status) {
      case "empty":
        ctx.fillStyle = "rgba(0, 200, 0, 0.25)"; // green
        ctx.strokeStyle = "#00b000";
        break;
      case "full":
        ctx.fillStyle = "rgba(255, 0, 0, 0.25)"; // red
        ctx.strokeStyle = "#cc0000";
        break;
      default: // unknown
        ctx.fillStyle = "rgba(255, 255, 0, 0.25)"; // yellow
        ctx.strokeStyle = "#cccc00";
        break;
    }
    ctx.lineWidth = 2;

    // === Draw polygon ===
    ctx.beginPath();
    poly.forEach(([x, y], k) => (k === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // === Draw corner dots ===
    poly.forEach(([x, y]) => {
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = "#fff";
      ctx.fill();
      ctx.strokeStyle = "rgba(0,0,0,0.3)";
      ctx.stroke();
    });

    // === Draw number label ===
    const cx = Math.round(poly.reduce((sum, p) => sum + p[0], 0) / poly.length);
    const cy = Math.round(poly.reduce((sum, p) => sum + p[1], 0) / poly.length);

    ctx.fillStyle = "rgba(0, 0, 0, 0.6)";
    ctx.fillRect(cx - 10, cy - 10, 20, 20);

    ctx.fillStyle = "#fff";
    ctx.font = "12px system-ui";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(spotNum, cx, cy);
  });

  // === Draft polygon (still red outline) ===
  if (draft.length) {
    ctx.strokeStyle = "#c22";
    ctx.fillStyle = "#f55";
    ctx.beginPath();
    draft.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
    ctx.stroke();
    draft.forEach(([x, y]) => {
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  // === HUD text ===
  ctx.fillStyle = "#333";
  ctx.font = "14px system-ui";
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
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
  if (polygons.length) { 
    polygons.pop(); setMsg("Removed last polygon.", "ok"); 
  }
  else{ 
    setMsg("No polygons.", "warn"); 
  }
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



/* === API === */

async function loadPolygons() {
  if (!lotId) throw new Error("Missing lotId");

  const r = await fetch(`${DB}/lots/${lotId}/spots`, {
    cache: "no-store" 
  });
  if (!r.ok) throw new Error(`Failed to load spots: ${
    r.status
  }`);
  const spots = await r.json();

  
  window._spots = spots;

  polygons = spots.map(s => {
    let p = s.polygon;         

    if (!p) return [];           

    // unwrap [[[x,y]...]] -> [[x,y]...]
    if (Array.isArray(p) && p.length === 1 && Array.isArray(p[0]) && Array.isArray(p[0][0])) {
      p = p[0];
    }

    // {x,y} -> [x,y], keep only valid pairs
    p = p.map(pt => {
      if (Array.isArray(pt) && pt.length === 2) return pt;
      if (pt && typeof pt === "object" && "x" in pt && "y" in pt) return [pt.x, pt.y];
      return null;
    }).filter(Boolean);

    // detect normalized 0..1 and scale up to canvas size
    const flat = p.flat().filter(n => typeof n === "number");
    const maxVal = flat.length ? Math.max(...flat) : 0;
    const normalized = maxVal <= 1.05;

    const W = canvas.width, H = canvas.height;
    const scaled = p.map(([x, y]) => normalized ? [Math.round(x * W), Math.round(y * H)] : [x, y]);

    return scaled.slice(0, 4); // your UI uses quads
  });

  // console.log("Loaded polygons:", polygons);
}


function toPoints(poly) {
  if (!Array.isArray(poly)) return [];
  return poly
    .map(pt => {
      if (Array.isArray(pt) && pt.length === 2 && isFinite(pt[0]) && isFinite(pt[1])) return [pt[0], pt[1]];
      if (pt && typeof pt === "object" && isFinite(pt.x) && isFinite(pt.y)) return [pt.x, pt.y];
      return null;
    })
    .filter(Boolean);
}


async function savePolygonsToDBSync(polys, { prune = true, statuses = null } = {}) {
  const payload = { polygons: polys.map(toPoints) };
  if (Array.isArray(statuses)) payload.statuses = statuses;

  const r = await fetch(`${DB}/lots/${lotId}/spots_sync?prune=${prune}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!r.ok) throw new Error(`Sync failed: ${r.status} ${await r.text()}`);
  return r.json();
}

btnSave.addEventListener("click", async () => {
  try {
    const res = await savePolygonsToDBSync(polygons, { prune: true /* or false to keep extra DB spots */ });
    
    setMsg(`Sync ok. added: ${res.added} / updated: ${res.updated} / deleted: ${res.deleted} / unchanged: ${res.unchanged}`, "ok");
    await loadPolygons();
    draw();
  } catch (e) {
    console.error(e);
    setMsg(`Save failed: ${e.message}`, "err");
  }
});


/* === UTIL === */
function setMsg(text, kind="ok") {
  msg.textContent = text;
  msg.style.color = kind === "ok" ? "#0a0" : kind === "warn" ? "#a60" : "#c00";
}

export async function fetchSpots(lotId) {
  const r = await fetch(`${DB}/lots/${lotId}/spots`, {
    cache: "no-store" 
  });
  if (!r.ok) throw new Error(`Failed to load spots: ${r.status}`);
  return r.json();
}


/* === INIT === */
(async function init(){
  try { await loadPolygons(); setMsg(`Loaded ${polygons.length} polygons.`, "ok"); }
  catch (e) { setMsg(`Initial load failed: ${e.message}`, "err"); }
  draw();
})();



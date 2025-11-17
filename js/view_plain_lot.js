// plain-view.js — read-only renderer matching the planner look

/* === CONFIG === */
const DB = "";
const BACKEND = "";
const FRAME_W = 960, FRAME_H = 540;     // canvas size used by your planner
const SLOT_W = 60,  SLOT_H = 100;       // same visual slot size as planner

// read lotId from URL (?id= or ?lotId=)
const _params = new URLSearchParams(location.search);
const _lotId = Number(_params.get("id") || _params.get("lotId"));

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/* === FETCH HELPERS === */
async function fetchPlainSlots(id) {
  const r = await fetch(`/lots/${id}/plain_slots`, { cache: "no-store" });
  if (!r.ok) throw new Error(`plain_slots ${r.status}`);
  return r.json(); // [{id, spot_id, slot_number, x, y, rotation}]
}
let lastStatusFetch = 0;
let statusInFlight = null;

async function fetchStatuses(id, preferBackend = true) {
  const MIN_GAP = 1500; // 1.5s minimum between stats calls
  const now = Date.now();

  // If we fetched too recently, wait the remaining time + jitter
  const elapsed = now - lastStatusFetch;
  if (elapsed < MIN_GAP) {
    const jitter = 200 + Math.random() * 400; // 200–600 ms
    await sleep(MIN_GAP - elapsed + jitter);
  }

  // If there’s already a stats request in flight, reuse it
  if (statusInFlight) {
    return statusInFlight;
  }

  statusInFlight = (async () => {
    try {
      if (preferBackend) {
        try {
          const r = await fetch(`/stats/${id}`, { cache: "no-store" });
          if (r.ok) {
            const j = await r.json(); // {spots:[{spot_id,status},...]}
            lastStatusFetch = Date.now();
            return new Map(j.spots.map((s) => [s.spot_id, s.status]));
          }
        } catch {
          // fall through to DB
        }
      }

      const r = await fetch(`/lots/${id}/spots`, { cache: "no-store" });
      if (!r.ok) throw new Error(`spots ${r.status}`);
      const j = await r.json(); // [{id,status},...]
      lastStatusFetch = Date.now();
      return new Map(j.map((s) => [s.id, s.status]));
    } finally {
      statusInFlight = null;
    }
  })();

  return statusInFlight;
}


/* === RENDER (READ-ONLY) === */
window.renderPlainLot = async function renderPlainLot({
  mountId = "plainView",
  lotId: id = _lotId,
  colorSource = "backend",            // "backend" | "db"
  width = FRAME_W,
  height = FRAME_H
} = {}) {
  if (!id) {
    console.error("Missing lotId (?id or ?lotId in URL, or pass {lotId})");
    return;
  }
  const mount = document.getElementById(mountId);
  if (!mount) return;

  const [slots, statuses] = await Promise.all([
    fetchPlainSlots(id),
    fetchStatuses(id, colorSource === "backend")
  ]);

  mount.innerHTML = "";
  if (!slots?.length) {
    mount.innerHTML = '<div style="color:#bbb;padding:8px">No plan slots yet.</div>';
    return;
  }

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");

  for (const sl of slots) {
    const cx = Number(sl.x), cy = Number(sl.y);
    const rot = Number(sl.rotation || 0);
    const raw = statuses.get(sl.spot_id) || "unknown";
    const status = raw === "occupied" ? "full" : raw;

    // box
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", cx - SLOT_W / 2);
    rect.setAttribute("y", cy - SLOT_H / 2);
    rect.setAttribute("width", SLOT_W);
    rect.setAttribute("height", SLOT_H);
    rect.setAttribute("rx", 6);
    rect.setAttribute("ry", 6);
    rect.setAttribute("transform", `rotate(${rot},${cx},${cy})`);
    rect.setAttribute("stroke", "#222");
    rect.setAttribute("stroke-width", "2");
    rect.setAttribute("data-spot-id", sl.spot_id); // for color refresh

    rect.setAttribute(
      "fill",
      status === "full" ? "#c0392b" :
      status === "empty" ? "#27ae60" : "#b7b300"
    );

    // label
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.textContent = sl.slot_number ?? "";
    label.setAttribute("x", cx);
    label.setAttribute("y", cy + 5);
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("fill", "#fff");
    label.setAttribute("font-size", "12");
    label.setAttribute("pointer-events", "none");

    svg.appendChild(rect);
    svg.appendChild(label);
  }

  mount.appendChild(svg);
};

/* === OPTIONAL: live color refresh without re-layout === */
window.refreshPlainLotColors = async function refreshPlainLotColors(
  mountId = "plainView",
  id = _lotId,
  preferBackend = true
) {
  const mount = document.getElementById(mountId);
  if (!mount) return;
  const statuses = await fetchStatuses(id, preferBackend);
  mount.querySelectorAll("rect[data-spot-id]").forEach(rect => {
    const spotId = Number(rect.getAttribute("data-spot-id"));
    const raw = statuses.get(spotId) || "unknown";
    const s = raw === "occupied" ? "full" : raw;
    rect.setAttribute(
      "fill",
      s === "full" ? "#c0392b" : s === "empty" ? "#27ae60" : "#b7b300"
    );
  });
};

/* === AUTO-RUN === */
renderPlainLot().catch(console.error);

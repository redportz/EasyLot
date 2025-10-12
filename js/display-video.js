// change if your server is elsewhere
const BACKEND = "http://127.0.0.1:5000";

const backendUrlText = document.getElementById("backendUrlText");
if (backendUrlText) backendUrlText.textContent = BACKEND;

/* STREAM */
const streamEl = document.getElementById("stream");
// add a timestamp to avoid browsers caching the first frame
if (streamEl) streamEl.src = `${BACKEND}/video_feed?ts=${Date.now()}`;

/*  STATS POLLER  */
const eleFree   = document.getElementById("free");
const eleFull   = document.getElementById("full");
const eleTotal  = document.getElementById("total");
const eleStatus = document.getElementById("lotStatus");
const eleUpdated= document.getElementById("updated");

function setStatus(free, full, total) {
  if (!eleStatus) return;
  if (eleFree)  eleFree.textContent  = free;
  if (eleFull)  eleFull.textContent  = full;
  if (eleTotal) eleTotal.textContent = total;

  let cls = "ok", txt = "Spaces Available";
  if (total === 0) { cls = "warn"; txt = "No Slots Configured"; }
  else if (free === 0) { cls = "bad"; txt = "Lot Full"; }
  else if (free <= Math.max(1, Math.round(total * 0.1))) { cls = "warn"; txt = "Limited Availability"; }

  eleStatus.className = `pill ${cls}`;
  eleStatus.textContent = txt;
}

async function fetchStats() {
  try {
    const res = await fetch(`${BACKEND}/stats`, { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    const j = await res.json();
    setStatus(j.free ?? 0, j.full ?? 0, j.total ?? 0);
    if (eleUpdated) eleUpdated.textContent = new Date().toLocaleTimeString();
  } catch (e) {
    if (eleStatus) {
      eleStatus.className = "pill bad";
      eleStatus.textContent = "Disconnected";
    }
    if (eleUpdated) eleUpdated.textContent = "";
  }
}

/* LIVE FEED SCALE — run after DOM so +/- always work */
document.addEventListener('DOMContentLoaded', () => {
  const stage   = document.getElementById("stage");
  const range   = document.getElementById("range");
  const minus   = document.getElementById("minus");
  const plus    = document.getElementById("plus");
  const zoomLbl = document.getElementById("zoomPct");

  if (!stage || !range || !minus || !plus) {
    console.error("Missing one of #stage #range #minus #plus");
    return;
  }

  function setScaleFrom(val){
    const pct = Math.max(25, Math.min(200, Number(val) || 100)); // clamp
    const s   = pct / 100;
    stage.style.setProperty("--scale", s);   // CSS var path
    stage.style.transform = `scale(${s})`;   // inline fallback
    range.value = pct;                       // keep slider in sync
    if (zoomLbl) zoomLbl.textContent = `${pct}%`;
  }

  range.addEventListener("input",  e => setScaleFrom(e.target.value));
  range.addEventListener("change", e => setScaleFrom(e.target.value));
  minus.addEventListener("click",  () => setScaleFrom(Number(range.value) - Number(range.step || 5)));
  plus .addEventListener("click",  () => setScaleFrom(Number(range.value) + Number(range.step || 5)));

  setScaleFrom(range.value); // init
});

/* start stats poller */
fetchStats();
setInterval(fetchStats, 1000);

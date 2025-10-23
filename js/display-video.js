// change if your server is elsewhere
const BACKEND = "http://127.0.0.1:5000"; 
/* STREAM  */
const streamEl = document.getElementById("stream");
// add a timestamp to avoid browsers caching the first frame
streamEl.src = `${BACKEND}/video_feed?ts=${Date.now()}`;

/*  STATS POLLER  */
const elFree = document.getElementById("free");
const elFull = document.getElementById("full");
const elTotal = document.getElementById("total");
const elStatus = document.getElementById("lotStatus");

function setStatus(free, full, total) {
  elFree.textContent = free;
  elFull.textContent = full;
  elTotal.textContent = total;

  let cls = "ok", txt = "Spaces Available";
  if (total === 0) { cls = "warn"; txt = "No Slots Configured"; }
  else if (free === 0) { cls = "bad"; txt = "Lot Full"; }
  else if (free <= Math.max(1, Math.round(total * 0.1))) { cls = "warn"; txt = "Limited Availability"; }

  elStatus.className = `pill ${cls}`;
  elStatus.textContent = txt;
}

async function fetchStats() {
  try {
    const res = await fetch(`${BACKEND}/stats`, { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    const j = await res.json();
    setStatus(j.free ?? 0, j.full ?? 0, j.total ?? 0);
  } catch (e) {
    elStatus.className = "pill bad";
    elStatus.textContent = "Disconnected";
  }
}





fetchStats();
setInterval(fetchStats, 1000);
const params = new URLSearchParams(window.location.search);
const lotId = params.get("id");

if (!lotId) {
  alert("Missing ?id= in URL.");
  window.location.href = "/index.html";
}


/* STREAM */
const streamEl = document.getElementById("stream");

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
    const res = await fetch(`/stats/${lotId}`, { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    const j = await res.json();
    setStatus(j.counts.free ?? 0, j.counts.full ?? 0, j.counts.total ?? 0);
  } catch (e) {
    console.error(e);
    elStatus.className = "pill bad";
    elStatus.textContent = "Disconnected";
  }
}

async function init() {
  try {
    const res = await fetch(`/lots/${lotId}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Lot not found");

    const lot = await res.json();
    console.log("Lot Info:", lot);

    // set video stream from DB value
    streamEl.src = `/live_video_feed/${lotId}?t=${Date.now()}`;
  if (lot.is_video_upside_down) {
    streamEl.style.transform = "rotate(180deg)";
  } else {
    streamEl.style.transform = "";
  }
  } catch (err) {
    console.error(err);
    alert("Error loading lot info.");
  }

  // start stats after we’ve tried to load the lot
  fetchStats();
  setInterval(fetchStats, 1000);
}

// assuming this script is at the bottom of <body>; otherwise wrap in DOMContentLoaded
init();

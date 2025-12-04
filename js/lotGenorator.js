document.getElementById("new-lot-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    let lotName = document.getElementById("Lot-name").value.trim();
    let liveUrl = document.getElementById("Url").value.trim();
    let selected = document.querySelector('input[name="yes_no"]:checked')?.value;
    let is_custom = document.querySelector('input[name="is_custom_yes_no"]:checked')?.value;
    const upside_down = selected === "true";
    const custom = is_custom === "true";
    if (!lotName || !liveUrl) {
        alert("Please fill in all fields.");
    return;
    }
    AddLotToList(lotName, liveUrl, upside_down, custom, event)
});

   
    


async function AddLotToList(lotName, liveUrl, upside_down, custom, event) {
   try {
        const res = await fetch("/lots", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: lotName, live_feed_url: liveUrl, is_video_upside_down: upside_down, is_custom:custom })
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.message || "Failed to create lot");
    }

    const data = await res.json();
    const lotId = data.id;


    const loading_overlay = document.getElementById("loading_overlay");
    loading_overlay.style.display = "block"
        setTimeout(() => {
      loading_overlay.style.display = "none";
      window.location.href = `./Edit-lot.html?id=${lotId}`;
    }, 20000);
  } catch (e) {
    console.error(e);
    overlay.remove();
    alert(e.message);
  }
    
}
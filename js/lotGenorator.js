document.getElementById("new-lot-form").addEventListener("submit", async (event) => {
    event.preventDefault();

    let lotName = document.getElementById("Lot-name").value.trim();
    let folder = document.getElementById("Folder-name").value.trim();
    let liveUrl = document.getElementById("Url").value.trim();

    if (!lotName || !folder || !liveUrl) {
        alert("Please fill in all fields.");
    return;
    }
    AddLotToList(lotName, folder, liveUrl, event)
    // CreateFolder(folderName);
});

   
    


async function AddLotToList(lotName, folder, liveUrl,event) {
   try {
        const res = await fetch("http://localhost:5000/lots", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: lotName, folder, live_feed_url: liveUrl })
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.message || "Failed to create lot");
    }

    alert("Lot created!");
    // optionally reset form
        event.target.reset();
    } catch (e) {
        console.error(e);
        alert(e.message);
  }
    
}

// function CreateFolder(folderName) {
    
//     CreatePolyFile()
//     CreateSpotInfoFile()
// }

// function CreatePolyFile() {
    
// }

// function CreateSpotInfoFile() {
    
// }
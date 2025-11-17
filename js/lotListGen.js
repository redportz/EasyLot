async function loadLots() {
  try {
    // Fetch your database data (could be /api/lots or local lots.json)
    const lotPath = '/lots'
    const res = await fetch(lotPath);
    const lots = await res.json();
    
    const list = document.getElementById('lot-list');


    lots.forEach(lot => {
      let lotId = lot.id;
      const li = document.createElement('li');
      lotId = lot.id;

      // main link
      const mainLink = document.createElement('a');
      mainLink.href = `/lot.html?id=${lotId}`;
      mainLink.textContent = lot.name;

      // edit link
        const role = localStorage.getItem("role");  
        if (role == "Admin") {
          const span = document.createElement('span');
          span.classList.add('edit');
          const editLink = document.createElement('a');
          editLink.href = `./admin/Edit-lot.html?id=${lotId}`;
          const icon = document.createElement('i');
          icon.classList.add('fa-solid', 'fa-pen-to-square');
          
      // delete button
          const deleteBtn = document.createElement('a');
          deleteBtn.classList.add('delete-btn');
          const deleteIcon = document.createElement('i');
          deleteIcon.classList.add('fa-solid', 'fa-trash');
          deleteBtn.appendChild(deleteIcon);

          deleteBtn.addEventListener('click', async (e) => {
            e.preventDefault();

            if(confirm(`Are you sure you want to delete lot "${lot.name}"?`)){
              try{
                const res = await fetch(`/lots/${lotId}`,{
                  method: "DELETE",
                  headers: {"Content-Type": "application/json"}
                });
                if (!res.ok) {
                  const err = await res.json().catch(() => ({}));
                  throw new Error(err.message || "Failed to delete lot");
                }
                li.remove();
                alert(`"${lot.name}" Deleted successfully`);
              }catch(err){
                console.error(err);
                alert("Error deleting lot: " + error.message)
              }
            }
          });
        
          editLink.appendChild(icon);
          span.appendChild(deleteBtn);
          span.appendChild(editLink);      
          li.appendChild(mainLink);
          li.appendChild(span);
          list.appendChild(li);
        }else{
          li.appendChild(mainLink);
          list.appendChild(li);
        }
      // put them together

    });
  } catch (err) {
    console.error('Failed to load lots:', err);
  }
}

loadLots();

async function loadLots() {
  try {
    // Fetch your database data (could be /api/lots or local lots.json)
    const lotPath = './json/lots.json'

    const res = await fetch(lotPath);
    const lots = await res.json();

    const list = document.getElementById('lot-list');


    lots.forEach(lot => {
      const li = document.createElement('li');

      // main link
      const mainLink = document.createElement('a');
      mainLink.href = `/${lot.folder}/lot.html`;
      mainLink.textContent = lot.name;

      // edit link
        const role = localStorage.getItem("role");  
        // console.log(role)
        if (role == "Admin") {
          const span = document.createElement('span');
          span.classList.add('edit');
          const editLink = document.createElement('a');
          editLink.href = './admin/Edit-lot.html';
          const icon = document.createElement('i');
          icon.classList.add('fa-solid', 'fa-pen-to-square');
          
          editLink.appendChild(icon);
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

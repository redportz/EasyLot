document.addEventListener("DOMContentLoaded", () => {
    const role = localStorage.getItem("role");
    console.log(role)
    const logBtn= document.getElementById("log-btn");
    if (role !=null) {
        logBtn.innerHTML = 
        `
        <a id="new-lot-btn" title="New Lot" href="/Admin/newLot.html"><i class="fa-solid fa-plus"></i></a>
        <a id="home-btn" title="Home" href="/index.html"><i class="fa-solid fa-house"></i></a>
            <a id="logout-btn" title="Log out" href="/login-page.html"><i class="fa-solid fa-right-to-bracket"></i></a>
        `;
    }
    else{
        logBtn.innerHTML =`
                <a id="home-btn" title="Home" href="/index.html"><i class="fa-solid fa-house"></i></a>
        <a id="login-btn" title="Log in" href="/login-page.html"><i class="fa-solid fa-right-to-bracket"></i></a>
    `
    }
});
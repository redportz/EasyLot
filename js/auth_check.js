(function() {
  document.documentElement.style.visibility = 'hidden';
  // Check if the user is logged in by looking for the "user" key in localStorage
  const userData = localStorage.getItem("user");
  const currentPath = window.location.pathname;
  // Parse the stored user data
    const user = JSON.parse(userData);
    if (!user || !user.role || currentPath.includes("/admin/") && user.role !== "Admin") {
            window.location.href = "/login-page.html";
            alert("Access Denied: You are not authorized to view that page.");
        }
    document.documentElement.style.visibility = 'visible';
})();
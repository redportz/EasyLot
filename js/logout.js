// Set auto-logout time to 5 minutes (in milliseconds)
const AUTO_LOGOUT_TIME = 5 *60* 1000; //remove the 60 to check logout timer. Will logout after 5 seconds
let logoutTimer;

// Function to reset the auto-logout timer
function resetLogoutTimer() {
  clearTimeout(logoutTimer);
  logoutTimer = setTimeout(() => {
    localStorage.removeItem("user");
    alert("Session expired. Please log in again.");
    window.location.href = "/login-page.html";
  }, AUTO_LOGOUT_TIME);
}

document.addEventListener("DOMContentLoaded", function() {
  // Check if the user is logged in by looking for the "user" key in localStorage
  const userData = localStorage.getItem("user");
  if (!userData) {
    // If no user is found, redirect to login
    window.location.href = "/login-page.html";
    return;
  }
  
  // Parse the stored user data
  const user = JSON.parse(userData);
  const currentPath = window.location.pathname;
  
  // If the current page is in the "/admin/" folder but the user's role isn't "Admin"
  if (currentPath.includes("/admin/") && user.role !== "Admin") {
    alert("Access Denied: You are not authorized to view this page.");
    window.location.href = "/login-page.html";
    return;
  }
  
  // Setup auto-logout timer and reset it on user interactions
  resetLogoutTimer();
  document.addEventListener("mousemove", resetLogoutTimer);
  document.addEventListener("keydown", resetLogoutTimer);
  
  // Optional: Attach logout behavior to a logout button
  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", function(event) {
      event.preventDefault();
      localStorage.removeItem("user");
      window.location.href = "/login-page.html";
    });
  }
});
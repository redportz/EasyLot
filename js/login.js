document.getElementById("login-form").addEventListener("submit", async function(event) {
    event.preventDefault(); // Prevent default form submission

    const enteredUsername = document.getElementById("Username").value;
    const enteredPassword = document.getElementById("password").value;
    let user=null;

    const useRealAPI=false;

    if (!useRealAPI) {
        const users = [
            { Username: "admin", Password: "supersecret", role: "Admin" },
        ];
    
        const user = users.find(u => u.Username === enteredUsername && u.Password === enteredPassword);
    
        if (!user) {
            alert("Login failed. Please try again.");
            return;
        }
    
        localStorage.setItem("role", user.role);
        handleLoginSuccess(user);
    }
    
    else{
        try {
            const response = await fetch(config.API_ENDPOINTS.login, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ email: enteredEmail, password: enteredPassword }) 
            });

            if (response.ok) {
                const result = await response.json();
                localStorage.setItem("userRole", result.role);
                
                handleLoginSuccess(result);
                
            } else {
                throw new Error(await response.text()); 
            }
        } catch (apiError) {
            console.error("API Call Failed:", apiError);
            alert("Login failed. Please try again.");
        }
    }
});

// 🔹 Function to handle login success, store user data & redirect
function handleLoginSuccess(user) {
    // Store user info for session use
    storeUserData(user);

    // Redirect based on role
    switch (user.role) {
        case "Admin":
            window.location.href = "./admin/homePage.html";
            break;
        default:
            alert("Unknown role. Please contact support.");
    }
}

function storeUserData(user) {
    localStorage.setItem("user", JSON.stringify(user));

}
// Show what JavaScript can actually read - HttpOnly cookies never appear here
const cookies = document.cookie;
console.log("document.cookie =", cookies);
document.getElementById("cookieOutput").textContent = cookies || "(no cookies visible to JavaScript)";

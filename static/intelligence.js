// Fetch intel reports with a manually entered Bearer token and append each one to the page
const fetchIntelButton = document.getElementById("fetchIntelButton");
const intelReports = document.getElementById("intelReports");

function addLine(parent, label, value) {
    const p = document.createElement("p");
    const strong = document.createElement("strong");
    strong.textContent = label + ": ";
    p.append(strong, document.createTextNode(value));
    parent.appendChild(p);
}

function renderReport(report) {
    const box = document.createElement("div");
    box.className = "intel-report";

    const title = document.createElement("h3");
    title.textContent = report.title;
    box.appendChild(title);

    addLine(box, "Classification", report.classification);
    addLine(box, "Role", report.role);
    addLine(box, "Generated at", report.generated_at);

    const list = document.createElement("ul");
    for (const finding of report.findings) {
        const li = document.createElement("li");
        li.textContent = finding; // textContent, not innerHTML -> no HTML injection
        list.appendChild(li);
    }
    box.appendChild(list);

    if (report.internal_notes) {
        addLine(box, "Internal notes", report.internal_notes);
    }
    // Newest report goes to the bottom; older ones stay
    intelReports.appendChild(box);
}

fetchIntelButton.addEventListener("click", async () => {
    const token = prompt("Enter your API token:");
    if (!token) {
        return; // cancelled or empty
    }
    try {
        const response = await fetch("/api/intelligence-feed", {
            headers: { Authorization: "Bearer " + token.trim() },
        });
        const data = await response.json();
        if (!response.ok) {
            alert(data.error || "Access Denied");
            return;
        }
        renderReport(data);
    } catch (err) {
        alert("Could not reach the server.");
    }
});

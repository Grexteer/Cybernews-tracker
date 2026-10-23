const hour = new Date().getHours();
let message = "";

if (hour < 12) {
    message = "Good Morning, Cyber Explorer!";
} else if (hour < 18) {
    message = "Good Afternoon, Cyber Defender!";
} else {
    message = "Good Evening, Night Watcher!";
}

console.log(message);
// Time-based greeting from Day 1, now personalised with the username from Flask
const greeting = document.getElementById("greeting");
const username = greeting.dataset.username;
greeting.textContent = message.split(",")[0] + ", " + username + "!";

// Dynamic news feed: local headlines on page load, live NewsAPI headlines on refresh
const refreshButton = document.getElementById("refreshButton");
const headlinesContainer = document.getElementById("headlinesContainer");
const newsStatus = document.getElementById("newsStatus");

const ERROR_MESSAGE = "News unavailable right now. Please try again later.";
const FALLBACK_MESSAGE = "Live news unavailable right now - showing saved headlines instead.";

async function fetchArticles(url) {
    const response = await fetch(url);
    // fetch only throws on network errors - HTTP errors (404, 500, 502...) must be checked by hand
    if (!response.ok) {
        throw new Error("HTTP " + response.status);
    }
    return response.json();
}

function showStatus(text, isError = false) {
    newsStatus.textContent = text;
    newsStatus.classList.toggle("error", isError);
}

async function loadLocalNews() {
    try {
        const articles = await fetchArticles("/api/news");
        renderHeadlines(articles);
        return true;
    } catch (error) {
        console.error("Loading local news failed:", error);
        headlinesContainer.replaceChildren();
        showStatus(ERROR_MESSAGE, true);
        return false;
    }
}

async function loadLiveNews() {
    showStatus("Loading live headlines...");
    refreshButton.disabled = true;

    try {
        const articles = await fetchArticles("/api/live-news");
        renderHeadlines(articles);
        showStatus(articles.length === 0 ? "No live headlines found." : "");
    } catch (error) {
        // Live API failed (invalid key, network issue...) -> fall back to the static news
        console.error("Loading live news failed, falling back to local news:", error);
        if (await loadLocalNews()) {
            showStatus(FALLBACK_MESSAGE, true);
        }
    } finally {
        refreshButton.disabled = false;
    }
}

function renderHeadlines(articles) {
    // Replace, don't append: clear the old headlines first
    headlinesContainer.replaceChildren();

    for (const article of articles) {
        const item = document.createElement("li");

        // textContent (not innerHTML) so titles from an external API can't inject HTML/scripts
        let title;
        if (isSafeLink(article.url)) {
            title = document.createElement("a");
            title.href = article.url;
            title.target = "_blank";
            title.rel = "noopener noreferrer";
        } else {
            title = document.createElement("span");  // local news has no URL
        }
        title.textContent = article.title;

        const source = document.createElement("span");
        source.className = "source";
        source.textContent = "Source: " + (article.source || "unknown");

        item.appendChild(title);
        item.appendChild(source);
        headlinesContainer.appendChild(item);
    }
}

function isSafeLink(url) {
    // Only allow real web links - blocks e.g. "javascript:..." URLs
    try {
        const parsed = new URL(url);
        return parsed.protocol === "https:" || parsed.protocol === "http:";
    } catch {
        return false;
    }
}

loadLocalNews();
refreshButton.addEventListener("click", loadLiveNews);

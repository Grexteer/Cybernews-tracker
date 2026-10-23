// Article list: loaded from /api/articles with fetch() and re-filtered while the user types
const filterForm = document.getElementById("filterForm");
const searchInput = document.getElementById("searchInput");
const categorySelect = document.getElementById("categorySelect");
const sourceSelect = document.getElementById("sourceSelect");
const articleList = document.getElementById("articleList");
const articleStatus = document.getElementById("articleStatus");

// Pre-fill the filters from the URL (?q=...&category=...&source=...)
const initialParams = new URLSearchParams(window.location.search);
searchInput.value = initialParams.get("q") || "";
categorySelect.value = initialParams.get("category") || "";
sourceSelect.value = initialParams.get("source") || "";

function renderArticles(articles) {
    articleList.replaceChildren();

    for (const article of articles) {
        const card = document.createElement("article");
        card.className = "card article-card";

        const badge = document.createElement("span");
        badge.className = "badge";
        badge.dataset.category = article.category;
        badge.textContent = article.category;

        const heading = document.createElement("h3");
        const link = document.createElement("a");
        link.href = "/article/" + encodeURIComponent(article.id);
        link.textContent = article.title; // textContent, not innerHTML -> no HTML injection
        heading.appendChild(link);

        const summary = document.createElement("p");
        summary.className = "summary";
        summary.textContent = article.summary;

        const meta = document.createElement("div");
        meta.className = "card-meta";
        const source = document.createElement("span");
        source.textContent = article.source;
        const time = document.createElement("time");
        time.dateTime = article.published;
        time.textContent = article.published;
        meta.append(source, time);

        card.append(badge, heading, summary, meta);
        articleList.appendChild(card);
    }
}

async function loadArticles() {
    const params = new URLSearchParams();
    if (searchInput.value.trim()) params.set("q", searchInput.value.trim());
    if (categorySelect.value) params.set("category", categorySelect.value);
    if (sourceSelect.value) params.set("source", sourceSelect.value);

    try {
        const response = await fetch("/api/articles?" + params);
        if (!response.ok) {
            throw new Error("HTTP " + response.status);
        }
        const articles = await response.json();
        renderArticles(articles);
        articleStatus.classList.remove("error");
        articleStatus.textContent = articles.length === 1 ? "1 article" : articles.length + " articles";
    } catch (error) {
        console.error("Loading articles failed:", error);
        articleList.replaceChildren();
        articleStatus.classList.add("error");
        articleStatus.textContent = "Articles could not be loaded. Please try again later.";
    }
}

let searchTimer;
searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer); // wait until the user stops typing
    searchTimer = setTimeout(loadArticles, 250);
});
categorySelect.addEventListener("change", loadArticles);
sourceSelect.addEventListener("change", loadArticles);
filterForm.addEventListener("submit", (event) => {
    event.preventDefault();
    loadArticles();
});

loadArticles();

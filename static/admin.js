// CSP blocks inline handlers, so the delete confirmation is attached here instead of onsubmit="..."
for (const form of document.querySelectorAll("form[data-confirm]")) {
    form.addEventListener("submit", (event) => {
        if (!confirm(form.dataset.confirm)) {
            event.preventDefault();
        }
    });
}

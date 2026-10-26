document.querySelectorAll("[data-editor-propose]").forEach((form) => {
    form.addEventListener("submit", () => {
        const button = form.querySelector("[data-editor-submit]");
        const waiting = form.querySelector("[data-editor-wait]");
        button.disabled = true;
        waiting.hidden = false;
        form.setAttribute("aria-busy", "true");
    });
});

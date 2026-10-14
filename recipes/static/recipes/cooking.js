(() => {
    const form = document.querySelector("[data-cooking-form]");
    if (!form) {
        return;
    }

    let submitted = false;
    form.addEventListener("submit", (event) => {
        if (submitted) {
            event.preventDefault();
            return;
        }

        submitted = true;
        window.setTimeout(() => {
            form.querySelectorAll('button[type="submit"]').forEach((button) => {
                button.disabled = true;
            });
        }, 0);
    });
})();

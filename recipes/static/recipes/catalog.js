(() => {
    const dataElement = document.getElementById("product-catalog-data");
    const search = document.getElementById("catalog-search");
    const grid = document.getElementById("catalog-grid");
    const selectedContainer = document.getElementById("catalog-selected");
    const count = document.getElementById("catalog-count");
    const clearButton = document.getElementById("catalog-clear");
    const emptySelection = document.getElementById("catalog-empty-selection");
    const emptyResults = document.getElementById("catalog-empty-results");

    if (
        !dataElement ||
        !search ||
        !grid ||
        !selectedContainer ||
        !count ||
        !clearButton ||
        !emptySelection ||
        !emptyResults
    ) {
        return;
    }

    const catalog = JSON.parse(dataElement.textContent);
    const labels = new Map(catalog.products.map((product) => [product.id, product]));
    const checkboxes = Array.from(grid.querySelectorAll('input[name="selected_products"]'));
    const categoryButtons = Array.from(document.querySelectorAll(".category-button"));
    let activeCategory = "all";

    function updateCatalog() {
        const query = search.value.trim().toLocaleLowerCase();
        let visibleCount = 0;
        grid.querySelectorAll(".product-card").forEach((card) => {
            const product = labels.get(card.dataset.productId);
            const searchableText = `${product.kk} ${product.ru}`.toLocaleLowerCase();
            const matchesCategory = activeCategory === "all" || card.dataset.category === activeCategory;
            card.hidden = !matchesCategory || !searchableText.includes(query);
            if (!card.hidden) {
                visibleCount += 1;
            }
        });
        emptyResults.hidden = visibleCount > 0;
    }

    function updateSelection() {
        const selected = checkboxes.filter((checkbox) => checkbox.checked);
        count.textContent = String(selected.length);
        emptySelection.hidden = selected.length > 0;
        selectedContainer.replaceChildren();

        selected.forEach((checkbox) => {
            const product = labels.get(checkbox.value);
            const tag = document.createElement("span");
            tag.className = "selected-tag";
            tag.textContent = product[catalog.language];
            selectedContainer.append(tag);
        });
    }

    categoryButtons.forEach((button) => {
        button.addEventListener("click", () => {
            activeCategory = button.dataset.category;
            categoryButtons.forEach((categoryButton) => {
                categoryButton.setAttribute(
                    "aria-pressed",
                    String(categoryButton === button),
                );
            });
            updateCatalog();
        });
    });

    search.addEventListener("input", updateCatalog);
    checkboxes.forEach((checkbox) => checkbox.addEventListener("change", updateSelection));
    clearButton.addEventListener("click", () => {
        checkboxes.forEach((checkbox) => {
            checkbox.checked = false;
        });
        updateSelection();
    });

    updateCatalog();
    updateSelection();
})();

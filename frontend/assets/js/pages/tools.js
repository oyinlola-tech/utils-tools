import {
    CATEGORY_META,
    CATEGORY_ORDER,
    loadCapabilities,
    toolsByCategory,
} from "../capabilities.js";
import { toolIconHtml, iconHtml } from "../icons.js";

let allTools = [];
let activeCategory = null;
let searchTerm = "";

function renderToolCard(tool) {
    const icon = toolIconHtml(tool.id);
    if (tool.status === "available") {
        const card = document.createElement("a");
        card.className = "tool-card";
        card.href = `/tools/${tool.id}`;
        card.dataset.toolId = tool.id;
        card.dataset.category = tool.category;
        card.innerHTML = `
            <div class="tool-card-top">
                <span class="tool-card-icon" aria-hidden="true">${icon}</span>
                <span class="tool-card-arrow" aria-hidden="true">${iconHtml("arrow-right")}</span>
            </div>
            <div>
                <span class="tool-card-label">${tool.category} tool</span>
                <h3>${tool.name}</h3>
                <p>${tool.description}</p>
            </div>
            <span class="tool-card-action">Open tool</span>`;
        return card;
    }

    const card = document.createElement("div");
    card.className = "tool-card tool-card-planned";
    card.dataset.toolId = tool.id;
    card.dataset.category = tool.category;
    const actionLabel =
        tool.status === "planned"
            ? "Coming soon"
            : "Unavailable in this environment";
    card.innerHTML = `
        <div class="tool-card-top">
            <span class="tool-card-icon" aria-hidden="true">${icon}</span>
        </div>
        <div>
            <span class="tool-card-label">${tool.category} tool</span>
            <h3>${tool.name}</h3>
            <p>${tool.description}</p>
        </div>
        <span class="tool-card-action">${actionLabel}</span>`;
    return card;
}

function matches(tool) {
    const inCategory = !activeCategory || tool.category === activeCategory;
    const term = searchTerm.trim().toLowerCase();
    const inSearch =
        !term ||
        tool.name.toLowerCase().includes(term) ||
        tool.description.toLowerCase().includes(term);
    return inCategory && inSearch;
}

function updateCount() {
    const host = document.querySelector("[data-tools-count]");
    if (!host) {
        return;
    }
    const visible = allTools.filter(matches).length;
    host.textContent = `${visible} of ${allTools.length} tools`;
    document.querySelectorAll("[data-tool-count]").forEach((el) => {
        el.textContent = String(allTools.filter((tool) => tool.status === "available").length);
    });
}

function applyFilter() {
    let anyVisible = false;
    document.querySelectorAll("[data-tool-card]").forEach((card) => {
        const tool = allTools.find((item) => item.id === card.dataset.toolId);
        const show = tool ? matches(tool) : false;
        card.hidden = !show;
        if (show) {
            anyVisible = true;
        }
    });
    document.querySelectorAll("[data-tool-card]").forEach((card) => {
        card.closest(".catalog-category").classList.toggle(
            "hidden",
            !card.closest(".catalog-category").querySelector("[data-tool-card]:not([hidden])")
        );
    });
    const empty = document.querySelector("[data-catalog-empty]");
    if (empty) {
        empty.hidden = anyVisible;
    }
    updateCount();
}

function renderCatalog() {
    const host = document.querySelector("#tool-catalog");
    if (!host) {
        return;
    }
    host.innerHTML = "";
    for (const category of CATEGORY_ORDER) {
        const meta = CATEGORY_META[category];
        if (!meta) {
            continue;
        }
        const tools = toolsByCategory(category);
        if (!tools.length) {
            continue;
        }
        const section = document.createElement("section");
        section.className = "catalog-category";
        section.id = `category-${category}`;

        const heading = document.createElement("div");
        heading.className = "catalog-category-heading";
        heading.innerHTML = `
            <h3>${meta.title}</h3>
            <p>${meta.description}</p>`;
        section.appendChild(heading);

        const grid = document.createElement("div");
        grid.className = "tool-grid catalog-grid";
        for (const tool of tools) {
            const card = renderToolCard(tool);
            card.setAttribute("data-tool-card", "");
            grid.appendChild(card);
        }
        section.appendChild(grid);
        host.appendChild(section);
    }

    const empty = document.createElement("p");
    empty.className = "catalog-empty";
    empty.setAttribute("data-catalog-empty", "");
    empty.textContent = "No tools match your search.";
    host.appendChild(empty);
}

function renderChips() {
    const host = document.querySelector("[data-filter-chips]");
    if (!host) {
        return;
    }
    const chips = [
        { id: null, label: "All tools" },
        ...CATEGORY_ORDER.map((category) => ({
            id: category,
            label: CATEGORY_META[category].title.replace(" tools", ""),
        })),
    ];
    host.innerHTML = "";
    for (const chip of chips) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "filter-chip";
        button.textContent = chip.label;
        button.setAttribute("aria-pressed", String(chip.id === activeCategory));
        button.addEventListener("click", () => {
            activeCategory = chip.id;
            host.querySelectorAll(".filter-chip").forEach((b) => {
                b.setAttribute("aria-pressed", String(b === button));
            });
            applyFilter();
        });
        host.appendChild(button);
    }
}

async function initToolsPage() {
    const host = document.querySelector("#tool-catalog");
    if (!host) {
        return;
    }
    try {
        const data = await loadCapabilities();
        allTools = data.tools;
    } catch (error) {
        host.innerHTML = `<p class="catalog-error" role="alert">
            Could not load the tool list. Start the local server and try again.
        </p>`;
        return;
    }

    const hashCategory = window.location.hash.replace("#category-", "");
    if (CATEGORY_ORDER.includes(hashCategory)) {
        activeCategory = hashCategory;
    }

    renderChips();
    renderCatalog();
    applyFilter();

    const searchInput = document.querySelector("[data-tools-search]");
    if (searchInput) {
        searchInput.addEventListener("input", (event) => {
            searchTerm = event.target.value;
            applyFilter();
        });
    }

    const target = document.querySelector(`#category-${activeCategory}`);
    if (target) {
        target.scrollIntoView({ block: "start" });
    }
}

initToolsPage();

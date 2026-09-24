import { openSupport } from "./support-popup.js";
import { injectIcons, iconHtml, brandIconHtml, toolIconHtml } from "./icons.js";
import {
    CATEGORY_META,
    CATEGORY_ORDER,
    loadCapabilities,
    tagHtml,
    toolsByCategory,
} from "./capabilities.js";

const GITHUB_URL = "https://github.com/oyinlola-tech/utils-tools";
const SITE_URL = "https://tools.oyinlola.site/";
const CLONE_URL = "git clone https://github.com/oyinlola-tech/utils-tools.git";

const NAV_ITEMS = [
    { href: "/about", label: "About" },
    { href: "/#how-it-works", label: "How it works" },
    { href: "/#faq", label: "FAQ" },
];

const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function brandHtml(className = "shell-brand") {
    return `
    <a href="/" class="${className}" aria-label="Utils-tool home">
      <img src="/static/assets/brand/logo-mark.svg" alt="" width="30" height="30" decoding="async" />
      <span>Utils<span class="shell-brand-dash">-</span>tool</span>
    </a>`;
}

function renderHeader() {
    const links = NAV_ITEMS.map(
        (item) =>
            `<a href="${item.href}" class="shell-nav-link" data-shell-nav-link>${item.label}</a>`
    ).join("");

    return `
<header class="shell-header" data-shell-header>
  <div class="shell-bar">
    ${brandHtml()}
    <nav class="shell-nav" aria-label="Main" data-shell-nav>
      <span class="shell-nav-indicator" aria-hidden="true" data-shell-nav-indicator></span>
      <button type="button" class="shell-nav-link shell-tools-toggle" data-shell-tools-toggle aria-expanded="false" aria-controls="shell-mega" aria-haspopup="true">
        Tools <span class="shell-tools-count" data-shell-tools-count></span> ${iconHtml("chevron-down")}
      </button>
      ${links}
    </nav>
    <div class="shell-actions">
      <button type="button" class="shell-search" data-shell-search aria-label="Search tools">
        ${iconHtml("magnifying-glass")}
        <span class="shell-search-label">Search tools</span>
        <kbd>${IS_MAC ? "⌘" : "Ctrl"} K</kbd>
      </button>
      <a href="${GITHUB_URL}" target="_blank" rel="noopener noreferrer" class="shell-github" aria-label="Utils-tool on GitHub">
        ${brandIconHtml("github")}
        <span>GitHub</span>
      </a>
      <button type="button" class="shell-menu-toggle" data-shell-menu-toggle aria-label="Open menu" aria-expanded="false" aria-controls="shell-mega">
        ${iconHtml("bars")}
      </button>
    </div>
  </div>
  <div id="shell-mega" class="shell-mega" data-shell-mega hidden>
    <div class="shell-mega-inner">
      <nav class="shell-mega-mobile-links" aria-label="Pages">
        <a href="/tools">All tools</a>
        ${NAV_ITEMS.map((item) => `<a href="${item.href}">${item.label}</a>`).join("")}
      </nav>
      <div class="shell-mega-layout">
        <div class="shell-mega-rail" role="tablist" aria-orientation="vertical" aria-label="Tool categories" data-shell-mega-rail></div>
        <div class="shell-mega-panel" role="tabpanel" data-shell-mega-panel>
          <p class="shell-mega-loading">Loading tools…</p>
        </div>
        <aside class="shell-mega-promo" aria-label="Find the right tool">
          <p class="shell-mega-promo-kicker">Not sure which tool?</p>
          <p class="shell-mega-promo-title">Drop your file on the home page and see every tool that fits it.</p>
          <a href="/#hero-title" class="shell-mega-promo-link">Open the file inspector ${iconHtml("arrow-right")}</a>
          <div class="shell-mega-popular" data-shell-mega-popular></div>
        </aside>
      </div>
      <div class="shell-mega-grid" data-shell-mega-grid></div>
      <div class="shell-mega-foot">
        <a href="/tools" class="shell-mega-all">Browse every tool ${iconHtml("arrow-right")}</a>
        <span class="shell-mega-hint">Tip: press <kbd>${IS_MAC ? "⌘" : "Ctrl"} K</kbd> anywhere to search.</span>
      </div>
    </div>
  </div>
</header>
<dialog class="shell-palette" data-shell-palette aria-label="Search tools">
  <div class="shell-palette-box">
    <div class="shell-palette-field">
      ${iconHtml("magnifying-glass")}
      <input type="search" placeholder="What do you need to do? e.g. compress, merge, png" aria-label="Search tools" autocomplete="off" spellcheck="false" data-shell-palette-input />
      <kbd>Esc</kbd>
    </div>
    <ul class="shell-palette-list" role="listbox" data-shell-palette-list></ul>
  </div>
</dialog>`;
}

function renderFooter() {
    return `
<footer class="shell-footer">
  <div class="shell-footer-inner">
    <div class="shell-footer-lead">
      <p class="shell-footer-pitch">Got a file? There is probably a tool for it.</p>
      <div class="shell-footer-cta">
        <a href="/tools" class="shell-footer-button">Browse all tools</a>
        <button type="button" class="shell-footer-ghost" data-shell-support>Support the project ${iconHtml("heart")}</button>
      </div>
    </div>
    <div class="shell-footer-columns" data-footer-columns></div>
    <div class="shell-footer-meta">
      <div class="shell-footer-links">
        <a href="/about">About</a>
        <a href="/#faq">FAQ</a>
        <a href="${GITHUB_URL}" target="_blank" rel="noopener noreferrer">Source on GitHub</a>
        <a href="${SITE_URL}" target="_blank" rel="noopener noreferrer">oyinlola.site</a>
        <button type="button" class="shell-footer-clone" data-shell-clone>${iconHtml("code")} <span>Copy clone command</span></button>
      </div>
      <p>© <span data-shell-year>2026</span> Oluwayemi Oyinlola · Open source · No accounts</p>
    </div>
  </div>
  <p class="shell-footer-wordmark" aria-hidden="true">Utils-tool</p>
</footer>
<button type="button" class="shell-fab" data-shell-support aria-label="Support this project">
  ${iconHtml("heart")}
  <span class="shell-fab-label">Support</span>
</button>`;
}

function currentPath() {
    const path = window.location.pathname;
    if (path === "/about") {
        return "/about";
    }
    if (path === "/tools" || path.startsWith("/tools/")) {
        return "/tools";
    }
    return path;
}

function markCurrentNav() {
    const current = currentPath();
    document.querySelectorAll("[data-shell-nav-link]").forEach((link) => {
        const href = link.getAttribute("href");
        // In-page anchors (/#faq) are sections, never "the current page".
        if (href && !href.includes("#") && href === current) {
            link.setAttribute("aria-current", "page");
        } else {
            link.removeAttribute("aria-current");
        }
    });
    const toolsToggle = document.querySelector("[data-shell-tools-toggle]");
    if (toolsToggle && current === "/tools") {
        toolsToggle.classList.add("is-current");
    }
}

function toolLinkHtml(tool) {
    return `
      <a href="/tools/${encodeURIComponent(tool.id)}" class="shell-tool-link">
        ${tagHtml(tool.category)}
        <span>${escapeHtml(tool.name)}</span>
      </a>`;
}

async function availableByCategory() {
    await loadCapabilities();
    return CATEGORY_ORDER.map((category) => ({
        category,
        meta: CATEGORY_META[category],
        tools: toolsByCategory(category).filter((tool) => tool.status === "available"),
    })).filter((group) => group.tools.length);
}

function currentToolId() {
    const match = /^\/tools\/([a-z0-9-]+)$/.exec(window.location.pathname);
    return match ? match[1] : null;
}

function categoryTitle(meta, category) {
    return (meta ? meta.title : category).replace(/ tools$/i, "");
}

function renderMegaPanel(panel, group) {
    const active = currentToolId();
    const { category, meta, tools } = group;
    panel.dataset.category = category;
    panel.setAttribute("aria-labelledby", `mega-tab-${category}`);
    panel.innerHTML = `
      <div class="shell-mega-panel-head">
        <p>${escapeHtml(meta ? meta.description : "")}</p>
        <a href="/tools#category-${category}" class="shell-mega-panel-all">All ${tools.length} ${escapeHtml(categoryTitle(meta, category).toLowerCase())} tools ${iconHtml("arrow-right")}</a>
      </div>
      <ul class="shell-mega-items">
        ${tools
            .map(
                (tool) => `
        <li><a href="/tools/${encodeURIComponent(tool.id)}" class="shell-mega-item" data-category="${category}"${tool.id === active ? ' aria-current="page"' : ""}>
          <span class="shell-mega-icon" aria-hidden="true">${toolIconHtml(tool.id)}</span>
          <span class="shell-mega-text">
            <span class="shell-mega-name">${escapeHtml(tool.name)}</span>
            <span class="shell-mega-desc">${escapeHtml(tool.description)}</span>
          </span>
        </a></li>`
            )
            .join("")}
      </ul>`;
}

let megaGroups = [];

function selectMegaCategory(category, { focus = false } = {}) {
    const rail = document.querySelector("[data-shell-mega-rail]");
    const panel = document.querySelector("[data-shell-mega-panel]");
    const group = megaGroups.find((item) => item.category === category);
    if (!rail || !panel || !group) {
        return;
    }
    rail.querySelectorAll("[role=tab]").forEach((tab) => {
        const selected = tab.dataset.category === category;
        tab.setAttribute("aria-selected", String(selected));
        tab.tabIndex = selected ? 0 : -1;
        if (selected && focus) {
            tab.focus();
        }
    });
    if (panel.dataset.category !== category) {
        renderMegaPanel(panel, group);
    }
}

async function fillMegaMenu() {
    const rail = document.querySelector("[data-shell-mega-rail]");
    const panel = document.querySelector("[data-shell-mega-panel]");
    const grid = document.querySelector("[data-shell-mega-grid]");
    const popular = document.querySelector("[data-shell-mega-popular]");
    if (!rail || !panel) {
        return;
    }
    try {
        megaGroups = await availableByCategory();
    } catch {
        panel.innerHTML = `<p class="shell-mega-loading">Tools could not be loaded. <a href="/tools">Open the tools page</a>.</p>`;
        return;
    }

    rail.innerHTML = megaGroups
        .map(
            ({ category, meta, tools }) => `
        <button type="button" role="tab" id="mega-tab-${category}" data-category="${category}"
            aria-selected="false" aria-controls="shell-mega-panel" tabindex="-1">
          ${tagHtml(category)}
          <span class="shell-mega-rail-name">${escapeHtml(categoryTitle(meta, category))}</span>
          <span class="shell-mega-rail-count">${tools.length}</span>
        </button>`
        )
        .join("");
    panel.id = "shell-mega-panel";

    // Mobile shows every group stacked instead of the rail + panel.
    if (grid) {
        grid.innerHTML = megaGroups
            .map(
                ({ category, meta, tools }) => `
          <section class="shell-mega-group" data-category="${category}">
            <h2>${escapeHtml(meta ? meta.title : category)}</h2>
            ${tools.map(toolLinkHtml).join("")}
          </section>`
            )
            .join("");
    }

    if (popular) {
        const featured = megaGroups.flatMap((group) => group.tools).filter((tool) => tool.featured).slice(0, 5);
        popular.innerHTML = featured.length
            ? `<p>Popular</p>${featured
                  .map((tool) => `<a href="/tools/${encodeURIComponent(tool.id)}">${escapeHtml(tool.name)}</a>`)
                  .join("")}`
            : "";
    }

    // Open on the category of the tool being viewed, otherwise the first.
    const activeTool = currentToolId();
    const start = megaGroups.find((group) => group.tools.some((tool) => tool.id === activeTool)) || megaGroups[0];
    selectMegaCategory(start.category);

    // Hovering a category switches the panel. A short delay stops a
    // diagonal move towards the panel from flicking through categories.
    let hoverTimer = null;
    rail.addEventListener("pointerover", (event) => {
        const tab = event.target.closest("[role=tab]");
        if (!tab || event.pointerType === "touch") {
            return;
        }
        clearTimeout(hoverTimer);
        hoverTimer = setTimeout(() => selectMegaCategory(tab.dataset.category), 70);
    });
    rail.addEventListener("pointerleave", () => clearTimeout(hoverTimer));
    rail.addEventListener("click", (event) => {
        const tab = event.target.closest("[role=tab]");
        if (tab) {
            selectMegaCategory(tab.dataset.category);
        }
    });
    rail.addEventListener("keydown", (event) => {
        const keys = ["ArrowDown", "ArrowUp", "Home", "End"];
        if (!keys.includes(event.key)) {
            return;
        }
        event.preventDefault();
        const tabs = Array.from(rail.querySelectorAll("[role=tab]"));
        const current = tabs.findIndex((tab) => tab.getAttribute("aria-selected") === "true");
        let next = current;
        if (event.key === "ArrowDown") next = (current + 1) % tabs.length;
        if (event.key === "ArrowUp") next = (current - 1 + tabs.length) % tabs.length;
        if (event.key === "Home") next = 0;
        if (event.key === "End") next = tabs.length - 1;
        selectMegaCategory(tabs[next].dataset.category, { focus: true });
    });
}

function setupMegaMenu() {
    const header = document.querySelector("[data-shell-header]");
    const mega = document.querySelector("[data-shell-mega]");
    const toolsToggle = document.querySelector("[data-shell-tools-toggle]");
    const menuToggle = document.querySelector("[data-shell-menu-toggle]");
    const toggles = [toolsToggle, menuToggle].filter(Boolean);
    if (!header || !mega) {
        return;
    }
    const canHover = window.matchMedia("(hover: hover) and (pointer: fine)");
    let filled = false;
    let openedByHover = false;
    let openTimer = null;
    let closeTimer = null;

    const warm = () => {
        if (!filled) {
            filled = true;
            fillMegaMenu();
        }
    };

    const setOpen = (open, { viaHover = false } = {}) => {
        clearTimeout(openTimer);
        clearTimeout(closeTimer);
        openedByHover = open && viaHover;
        if (mega.hidden === !open) {
            return;
        }
        mega.hidden = !open;
        header.classList.toggle("is-open", open);
        toggles.forEach((toggle) => toggle.setAttribute("aria-expanded", String(open)));
        if (menuToggle) {
            menuToggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
            menuToggle.innerHTML = iconHtml(open ? "xmark" : "bars");
        }
        if (open) {
            warm();
        }
    };

    toggles.forEach((toggle) =>
        toggle.addEventListener("click", (event) => {
            event.stopPropagation();
            if (toggle === toolsToggle && openedByHover && !mega.hidden) {
                // Clicking a menu that hover already opened pins it open.
                openedByHover = false;
                return;
            }
            setOpen(mega.hidden);
        })
    );

    if (toolsToggle) {
        // Hover intent: open after a short pause, close after the pointer
        // has been gone for a moment, so passing over the bar never flickers.
        toolsToggle.addEventListener("pointerenter", (event) => {
            if (event.pointerType !== "mouse" || !canHover.matches) {
                return;
            }
            warm();
            clearTimeout(closeTimer);
            if (mega.hidden) {
                openTimer = setTimeout(() => setOpen(true, { viaHover: true }), 90);
            }
        });
        toolsToggle.addEventListener("pointerleave", () => clearTimeout(openTimer));
    }

    header.addEventListener("pointerenter", () => clearTimeout(closeTimer));
    header.addEventListener("pointerleave", (event) => {
        if (event.pointerType === "mouse" && openedByHover) {
            closeTimer = setTimeout(() => setOpen(false), 260);
        }
    });

    // Hovering a sibling nav link closes a hover-opened menu, like any
    // desktop menu bar.
    document.querySelectorAll("[data-shell-nav-link]").forEach((link) =>
        link.addEventListener("pointerenter", () => {
            if (openedByHover) {
                setOpen(false);
            }
        })
    );

    mega.addEventListener("click", (event) => {
        if (event.target.closest("a")) {
            setOpen(false);
        }
    });

    document.addEventListener("click", (event) => {
        if (!mega.hidden && !event.target.closest("[data-shell-header]")) {
            setOpen(false);
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !mega.hidden) {
            setOpen(false);
            const toggle = window.innerWidth > 860 ? toolsToggle : menuToggle;
            if (toggle) {
                toggle.focus();
            }
        }
    });

    if (toolsToggle) {
        toolsToggle.addEventListener("keydown", (event) => {
            if (event.key === "ArrowDown") {
                event.preventDefault();
                setOpen(true);
                const focusRail = () => {
                    const tab = document.querySelector("[data-shell-mega-rail] [aria-selected=true]");
                    if (tab) {
                        tab.focus();
                    } else {
                        setTimeout(focusRail, 50);
                    }
                };
                focusRail();
            }
        });
    }

    if (window.location.pathname === "/") {
        header.classList.add("is-home");
    }
    const onScroll = () => header.classList.toggle("is-scrolled", window.scrollY > 8);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    loadCapabilities()
        .then((data) => {
            const count = data.tools.filter((tool) => tool.status === "available").length;
            const badge = document.querySelector("[data-shell-tools-count]");
            if (badge && count) {
                badge.textContent = String(count);
            }
        })
        .catch(() => {});
}

// A pill that glides to whichever top-level link is under the pointer and
// rests on the current page's link.
function setupNavIndicator() {
    const nav = document.querySelector("[data-shell-nav]");
    const indicator = document.querySelector("[data-shell-nav-indicator]");
    if (!nav || !indicator) {
        return;
    }
    const items = () => Array.from(nav.querySelectorAll(".shell-nav-link"));
    const place = (target, instant = false) => {
        if (!target) {
            indicator.style.opacity = "0";
            return;
        }
        if (instant) {
            indicator.style.transition = "none";
        }
        indicator.style.width = `${target.offsetWidth}px`;
        indicator.style.transform = `translateX(${target.offsetLeft}px)`;
        indicator.style.opacity = "1";
        indicator.classList.toggle("is-current", target.matches("[aria-current], .is-current"));
        if (instant) {
            void indicator.offsetWidth;
            indicator.style.transition = "";
        }
    };
    const resting = () =>
        items().find((item) => item.matches("[aria-current], .is-current, [aria-expanded=true]")) || null;

    nav.classList.add("has-indicator");
    place(resting(), true);
    nav.addEventListener("pointerover", (event) => {
        const link = event.target.closest(".shell-nav-link");
        if (link) {
            place(link);
        }
    });
    nav.addEventListener("pointerleave", () => place(resting()));
    nav.addEventListener("focusin", (event) => {
        const link = event.target.closest(".shell-nav-link");
        if (link) {
            place(link);
        }
    });
    nav.addEventListener("focusout", () => place(resting()));
    const toolsToggle = nav.querySelector("[data-shell-tools-toggle]");
    if (toolsToggle) {
        new MutationObserver(() => {
            if (!nav.matches(":hover")) {
                place(resting());
            }
        }).observe(toolsToggle, { attributes: true, attributeFilter: ["aria-expanded"] });
    }
    window.addEventListener("resize", () => place(resting(), true));
    if (document.fonts && document.fonts.ready) {
        document.fonts.ready.then(() => place(resting(), true));
    }
}

function scoreTool(tool, words) {
    const name = tool.name.toLowerCase();
    const haystack = `${name} ${tool.id} ${tool.category} ${tool.description}`.toLowerCase();
    let score = 0;
    for (const word of words) {
        if (!haystack.includes(word)) {
            return -1;
        }
        if (name.startsWith(word)) {
            score += 3;
        } else if (name.includes(word)) {
            score += 2;
        } else {
            score += 1;
        }
    }
    return score;
}

function setupPalette() {
    const dialog = document.querySelector("[data-shell-palette]");
    const input = document.querySelector("[data-shell-palette-input]");
    const list = document.querySelector("[data-shell-palette-list]");
    if (!dialog || !input || !list || typeof dialog.showModal !== "function") {
        return;
    }
    let tools = [];
    let results = [];
    let active = 0;

    const render = () => {
        const words = input.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
        results = tools
            .map((tool) => ({ tool, score: words.length ? scoreTool(tool, words) : 0 }))
            .filter((item) => item.score >= 0)
            .sort((a, b) => b.score - a.score)
            .slice(0, 8)
            .map((item) => item.tool);
        active = Math.min(active, Math.max(results.length - 1, 0));
        if (!results.length) {
            list.innerHTML = `<li class="shell-palette-empty">No tool matches “${escapeHtml(input.value.trim())}”. Try a file type like “pdf” or an action like “resize”.</li>`;
            input.removeAttribute("aria-activedescendant");
            return;
        }
        list.innerHTML = results
            .map(
                (tool, index) => `
          <li role="option" id="palette-opt-${index}" aria-selected="${index === active}" data-index="${index}">
            <a href="/tools/${encodeURIComponent(tool.id)}" tabindex="-1">
              ${tagHtml(tool.category)}
              <span class="shell-palette-name">${escapeHtml(tool.name)}</span>
              <span class="shell-palette-desc">${escapeHtml(tool.description)}</span>
            </a>
          </li>`
            )
            .join("");
        input.setAttribute("aria-activedescendant", `palette-opt-${active}`);
    };

    const open = async () => {
        if (dialog.open) {
            return;
        }
        input.value = "";
        active = 0;
        dialog.showModal();
        input.focus();
        try {
            const groups = await availableByCategory();
            tools = groups.flatMap((group) => group.tools);
        } catch {
            tools = [];
        }
        render();
    };

    document.querySelectorAll("[data-shell-search]").forEach((button) =>
        button.addEventListener("click", open)
    );

    document.addEventListener("keydown", (event) => {
        if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
            event.preventDefault();
            open();
        } else if (event.key === "/" && !event.target.closest("input, textarea, select, [contenteditable]")) {
            event.preventDefault();
            open();
        }
    });

    input.addEventListener("input", () => {
        active = 0;
        render();
    });

    input.addEventListener("keydown", (event) => {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            if (!results.length) {
                return;
            }
            const step = event.key === "ArrowDown" ? 1 : -1;
            active = (active + step + results.length) % results.length;
            render();
            const option = list.querySelector(`[data-index="${active}"]`);
            if (option) {
                option.scrollIntoView({ block: "nearest" });
            }
        } else if (event.key === "Enter" && results[active]) {
            event.preventDefault();
            window.location.href = `/tools/${encodeURIComponent(results[active].id)}`;
        }
    });

    list.addEventListener("pointermove", (event) => {
        const option = event.target.closest("[data-index]");
        if (option && Number(option.dataset.index) !== active) {
            active = Number(option.dataset.index);
            list.querySelectorAll("[role=option]").forEach((el) =>
                el.setAttribute("aria-selected", String(Number(el.dataset.index) === active))
            );
            input.setAttribute("aria-activedescendant", `palette-opt-${active}`);
        }
    });

    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) {
            dialog.close();
        }
    });
}

function copyText(value) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(value);
    }
    return new Promise((resolve, reject) => {
        const input = document.createElement("textarea");
        input.value = value;
        input.setAttribute("readonly", "");
        input.style.position = "fixed";
        input.style.opacity = "0";
        document.body.appendChild(input);
        input.select();
        try {
            document.execCommand("copy");
            input.remove();
            resolve();
        } catch (error) {
            input.remove();
            reject(error);
        }
    });
}

function setupClone() {
    document.querySelectorAll("[data-shell-clone]").forEach((button) => {
        button.addEventListener("click", async () => {
            const original = button.innerHTML;
            try {
                await copyText(CLONE_URL);
                button.innerHTML = `${iconHtml("check")} <span>Copied clone command</span>`;
            } catch {
                button.innerHTML = `${iconHtml("triangle-exclamation")} <span>Copy failed</span>`;
            }
            window.setTimeout(() => {
                button.innerHTML = original;
            }, 2000);
        });
    });
}

async function renderFooterColumns() {
    const host = document.querySelector("[data-footer-columns]");
    if (!host) {
        return;
    }
    try {
        const groups = await availableByCategory();
        host.innerHTML = groups
            .map(
                ({ category, meta, tools }) => `
          <section class="shell-footer-column" data-category="${category}">
            <h2>${tagHtml(category)} ${escapeHtml(meta ? meta.title.replace(/ tools$/i, "") : category)}</h2>
            ${tools
                .slice(0, 6)
                .map((tool) => `<a href="/tools/${encodeURIComponent(tool.id)}">${escapeHtml(tool.name)}</a>`)
                .join("")}
            ${tools.length > 6 ? `<a href="/tools#category-${category}" class="shell-footer-more">+${tools.length - 6} more</a>` : ""}
          </section>`
            )
            .join("");
    } catch {
        host.innerHTML = "";
    }
}

export function renderShell() {
    injectIcons();

    const headerHost = document.querySelector("#site-header");
    const footerHost = document.querySelector("#site-footer");

    if (headerHost) {
        headerHost.innerHTML = renderHeader();
    }
    if (footerHost) {
        footerHost.innerHTML = renderFooter();
        const year = footerHost.querySelector("[data-shell-year]");
        if (year) {
            year.textContent = String(new Date().getFullYear());
        }
        renderFooterColumns();
    }

    const main = document.querySelector("main");
    if (main && !main.id) {
        main.id = "main";
    }

    if (!document.querySelector(".skip-link")) {
        const skipLink = document.createElement("a");
        skipLink.className = "skip-link";
        skipLink.href = "#main";
        skipLink.textContent = "Skip to content";
        document.body.prepend(skipLink);
    }

    markCurrentNav();
    setupMegaMenu();
    setupNavIndicator();
    setupPalette();
    setupClone();

    document.querySelectorAll("[data-shell-support]").forEach((button) => {
        button.addEventListener("click", () => openSupport());
    });
}

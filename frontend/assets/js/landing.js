import { renderShell } from "./shell.js";
import {
    CATEGORY_META,
    CATEGORY_ORDER,
    CATEGORY_TAG,
    availableTools,
    loadCapabilities,
    tagHtml,
    toolsByCategory,
} from "./capabilities.js";
import { stashFiles } from "./handoff.js";
import { formatBytes } from "./utils.js";

renderShell();

const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

/* ---------------- File inspector ---------------- */

// Tools that can take each kind of file, best first. Only tools whose page
// has the shared upload box receive the dropped file automatically.
const TOOLS_FOR = {
    image: [
        "image-compressor", "image-converter", "image-resizer", "image-cropper",
        "background-remover", "metadata-remover", "image-editor", "watermark",
        "image-to-pdf", "social-media-resizer", "palette-extractor", "svg-generator",
        "favicon-generator", "background-replacement", "screenshot-beautifier",
        "image-to-base64", "file-analyzer", "hash-generator",
    ],
    pdf: [
        "pdf-compressor", "pdf-merger", "pdf-splitter", "pdf-to-image", "pdf-rotator",
        "pdf-extractor", "pdf-encrypt", "pdf-page-number", "pdf-watermark",
        "file-analyzer", "hash-generator",
    ],
    svg: ["svg-optimizer", "image-to-base64", "file-analyzer", "hash-generator"],
    json: ["json-formatter", "json-csv-converter", "file-analyzer", "hash-generator"],
    csv: ["json-csv-converter", "file-analyzer", "hash-generator"],
    other: ["file-analyzer", "zip-creator", "duplicate-finder", "hash-generator"],
};

const HANDOFF_TOOLS = new Set([
    "image-compressor", "pdf-compressor", "background-remover",
    "image-converter", "image-resizer", "image-cropper", "metadata-remover", "image-editor",
    "watermark", "image-to-pdf", "social-media-resizer", "palette-extractor", "svg-generator",
    "favicon-generator", "background-replacement", "screenshot-beautifier", "image-to-base64",
    "file-analyzer", "zip-creator", "duplicate-finder", "pdf-merger", "pdf-splitter",
    "pdf-to-image", "pdf-rotator", "pdf-extractor", "pdf-encrypt", "pdf-page-number",
    "pdf-watermark", "svg-optimizer",
]);

const SIGNATURES = [
    { kind: "image", label: "JPEG image", test: (b) => b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff },
    { kind: "image", label: "PNG image", test: (b) => b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4e && b[3] === 0x47 },
    { kind: "image", label: "GIF image", test: (b) => b[0] === 0x47 && b[1] === 0x49 && b[2] === 0x46 },
    { kind: "image", label: "WebP image", test: (b) => ascii(b, 0, 4) === "RIFF" && ascii(b, 8, 12) === "WEBP" },
    { kind: "image", label: "AVIF image", test: (b) => ascii(b, 4, 8) === "ftyp" && /avi[fs]/.test(ascii(b, 8, 12)) },
    { kind: "image", label: "BMP image", test: (b) => b[0] === 0x42 && b[1] === 0x4d },
    { kind: "pdf", label: "PDF document", test: (b) => ascii(b, 0, 5) === "%PDF-" },
    { kind: "other", label: "ZIP archive", test: (b) => b[0] === 0x50 && b[1] === 0x4b && b[2] === 0x03 && b[3] === 0x04 },
    { kind: "other", label: "MP4 / MOV video", test: (b) => ascii(b, 4, 8) === "ftyp" },
];

function ascii(bytes, from, to) {
    return String.fromCharCode(...bytes.slice(from, to));
}

async function identify(file) {
    const head = new Uint8Array(await file.slice(0, 512).arrayBuffer());
    const hex = Array.from(head.slice(0, 8), (byte) => byte.toString(16).padStart(2, "0").toUpperCase());
    for (const signature of SIGNATURES) {
        if (signature.test(head)) {
            return { kind: signature.kind, label: signature.label, hex };
        }
    }
    const text = new TextDecoder("utf-8", { fatal: false }).decode(head).trimStart();
    const name = file.name.toLowerCase();
    if (/^(<\?xml[^>]*>\s*)?(<!--[\s\S]*?-->\s*)*<svg/i.test(text) || name.endsWith(".svg")) {
        return { kind: "svg", label: "SVG vector image", hex };
    }
    if (/^[[{]/.test(text) && (name.endsWith(".json") || /^[[{]\s*["[{\d-]/.test(text))) {
        return { kind: "json", label: "JSON data", hex };
    }
    if (name.endsWith(".csv")) {
        return { kind: "csv", label: "CSV table", hex };
    }
    const printable = head.length && head.every((byte) => byte === 9 || byte === 10 || byte === 13 || byte >= 32);
    return { kind: "other", label: printable ? "Plain text" : "Unrecognised binary file", hex };
}

async function imageSize(file) {
    try {
        const bitmap = await createImageBitmap(file);
        const size = `${bitmap.width} × ${bitmap.height}px`;
        bitmap.close();
        return size;
    } catch {
        return null;
    }
}

function setupInspector() {
    const root = document.querySelector("[data-inspector]");
    const drop = document.querySelector("[data-inspector-drop]");
    const input = document.querySelector("#inspector-input");
    const empty = document.querySelector("[data-inspector-empty]");
    const report = document.querySelector("[data-inspector-report]");
    if (!root || !drop || !input) {
        return;
    }
    let previewUrl = null;

    const reset = () => {
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
            previewUrl = null;
        }
        report.classList.add("hidden");
        report.innerHTML = "";
        empty.classList.remove("hidden");
        root.classList.remove("has-file");
    };

    const inspect = async (file) => {
        if (!file) {
            return;
        }
        root.classList.add("is-reading");
        const [info, size] = await Promise.all([
            identify(file),
            file.type.startsWith("image/") ? imageSize(file) : Promise.resolve(null),
        ]);
        await loadCapabilities().catch(() => null);
        const available = new Map(availableTools().map((tool) => [tool.id, tool]));
        const tools = (TOOLS_FOR[info.kind] || TOOLS_FOR.other)
            .map((id) => available.get(id))
            .filter(Boolean);

        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
        }
        previewUrl = info.kind === "image" || info.kind === "svg" ? URL.createObjectURL(file) : null;

        const facts = [formatBytes(file.size), size].filter(Boolean).join(" · ");
        report.innerHTML = `
            <div class="lp-report-file">
                ${previewUrl
                    ? `<img src="${previewUrl}" alt="" class="lp-report-thumb" />`
                    : `<span class="lp-report-thumb lp-report-ext">${escapeHtml((file.name.split(".").pop() || "file").slice(0, 4).toUpperCase())}</span>`}
                <div class="lp-report-text">
                    <p class="lp-report-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</p>
                    <p class="lp-report-kind">${escapeHtml(info.label)} · ${escapeHtml(facts)}</p>
                </div>
                <button type="button" class="lp-report-clear" data-inspector-clear aria-label="Inspect a different file">✕</button>
            </div>
            <p class="lp-report-bytes" aria-label="First bytes of the file">
                ${info.hex.map((byte) => `<span>${byte}</span>`).join("")}
                <em>signature</em>
            </p>
            <p class="lp-report-count">${tools.length
                ? `${tools.length} ${tools.length === 1 ? "tool fits" : "tools fit"} this file — pick one:`
                : "No tool here works with this file type yet."}</p>
            <ul class="lp-report-tools">
                ${tools
                    .map(
                        (tool) => `
                <li><a href="/tools/${encodeURIComponent(tool.id)}" data-tool-id="${escapeHtml(tool.id)}">
                    ${tagHtml(tool.category)}<span>${escapeHtml(tool.name)}</span><span class="lp-arrow" aria-hidden="true">→</span>
                </a></li>`
                    )
                    .join("")}
            </ul>`;
        empty.classList.add("hidden");
        report.classList.remove("hidden");
        root.classList.remove("is-reading");
        root.classList.add("has-file");
        report.querySelector("[data-inspector-clear]").addEventListener("click", reset);
        report.querySelectorAll("[data-tool-id]").forEach((link) => {
            link.addEventListener("click", async (event) => {
                if (!HANDOFF_TOOLS.has(link.dataset.toolId)) {
                    return;
                }
                event.preventDefault();
                await stashFiles([file]);
                window.location.href = link.href;
            });
        });
    };

    input.addEventListener("change", () => {
        inspect(input.files && input.files[0]);
        input.value = "";
    });

    drop.addEventListener("click", (event) => {
        if (!root.classList.contains("has-file") && !event.target.closest("label, a, button, input")) {
            input.click();
        }
    });
    drop.addEventListener("keydown", (event) => {
        if ((event.key === "Enter" || event.key === " ") && event.target === drop) {
            event.preventDefault();
            input.click();
        }
    });

    let depth = 0;
    const targets = [document.documentElement];
    targets.forEach((target) => {
        target.addEventListener("dragenter", (event) => {
            if (!Array.from(event.dataTransfer?.types || []).includes("Files")) {
                return;
            }
            depth += 1;
            root.classList.add("is-dragging");
        });
        target.addEventListener("dragleave", () => {
            depth = Math.max(0, depth - 1);
            if (!depth) {
                root.classList.remove("is-dragging");
            }
        });
        target.addEventListener("dragover", (event) => event.preventDefault());
        target.addEventListener("drop", (event) => {
            event.preventDefault();
            depth = 0;
            root.classList.remove("is-dragging");
            const file = event.dataTransfer?.files?.[0];
            if (file) {
                inspect(file);
                root.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        });
    });

    document.addEventListener("paste", (event) => {
        if (event.target.closest && event.target.closest("input, textarea, [contenteditable]")) {
            return;
        }
        const file = event.clipboardData?.files?.[0];
        if (file) {
            event.preventDefault();
            inspect(file);
        }
    });
}

/* ---------------- Catalog tabs ---------------- */

function renderCatalog() {
    const tabsHost = document.querySelector("[data-catalog-tabs]");
    const panel = document.querySelector("[data-catalog-panel]");
    if (!tabsHost || !panel) {
        return;
    }
    const groups = CATEGORY_ORDER.map((category) => ({
        category,
        tools: toolsByCategory(category).filter((tool) => tool.status === "available"),
    })).filter((group) => group.tools.length);

    if (!groups.length) {
        panel.innerHTML = `<p class="lp-muted">Tools couldn't be loaded. <a href="/tools" class="lp-link">Open the catalog</a>.</p>`;
        return;
    }

    tabsHost.innerHTML = groups
        .map(
            ({ category, tools }, index) => `
        <button type="button" role="tab" id="tab-${category}" data-category="${category}"
            aria-selected="${index === 0}" aria-controls="catalog-panel" tabindex="${index === 0 ? 0 : -1}">
            <span class="file-tag">${CATEGORY_TAG[category]}</span>
            ${escapeHtml((CATEGORY_META[category]?.title || category).replace(/ tools$/i, ""))}
            <span class="lp-tab-count">${tools.length}</span>
        </button>`
        )
        .join("");
    panel.id = "catalog-panel";

    const show = (category) => {
        const group = groups.find((item) => item.category === category);
        tabsHost.querySelectorAll("[role=tab]").forEach((tab) => {
            const selected = tab.dataset.category === category;
            tab.setAttribute("aria-selected", String(selected));
            tab.tabIndex = selected ? 0 : -1;
        });
        panel.setAttribute("aria-labelledby", `tab-${category}`);
        panel.dataset.category = category;
        panel.innerHTML = `
            <p class="lp-panel-desc">${escapeHtml(CATEGORY_META[category]?.description || "")}</p>
            <ul class="lp-tool-grid">
                ${group.tools
                    .map(
                        (tool) => `
                <li><a href="/tools/${encodeURIComponent(tool.id)}" class="lp-tool">
                    <span class="lp-tool-name">${escapeHtml(tool.name)}</span>
                    <span class="lp-tool-desc">${escapeHtml(tool.description)}</span>
                    <span class="lp-arrow" aria-hidden="true">→</span>
                </a></li>`
                    )
                    .join("")}
            </ul>`;
    };

    tabsHost.addEventListener("click", (event) => {
        const tab = event.target.closest("[role=tab]");
        if (tab) {
            show(tab.dataset.category);
        }
    });
    tabsHost.addEventListener("keydown", (event) => {
        if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) {
            return;
        }
        event.preventDefault();
        const tabs = Array.from(tabsHost.querySelectorAll("[role=tab]"));
        const current = tabs.findIndex((tab) => tab.getAttribute("aria-selected") === "true");
        let next = current;
        if (event.key === "ArrowRight") next = (current + 1) % tabs.length;
        if (event.key === "ArrowLeft") next = (current - 1 + tabs.length) % tabs.length;
        if (event.key === "Home") next = 0;
        if (event.key === "End") next = tabs.length - 1;
        tabs[next].focus();
        show(tabs[next].dataset.category);
    });

    show(groups[0].category);
}

async function init() {
    document.querySelectorAll(".lp-hero-actions kbd").forEach((kbd) => {
        kbd.textContent = IS_MAC ? "⌘ K" : "Ctrl K";
    });
    setupInspector();
    try {
        await loadCapabilities();
    } catch {
        renderCatalog();
        return;
    }
    const count = availableTools().length;
    document.querySelectorAll("[data-tool-count]").forEach((el) => {
        el.textContent = String(count);
    });
    renderCatalog();
}

init();

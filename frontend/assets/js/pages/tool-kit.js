import { renderShell } from "../shell.js";
import { loadCapabilities, getTool } from "../capabilities.js";
import {
    ErrorBanner,
    ProcessingPanel,
    UploadZone,
    createDownloadCard,
} from "../components/ui.js";
import { showElement, hideElement, formatBytes } from "../utils.js";

const ERROR_PAGES = [400, 404, 408, 413, 415, 422, 429, 500, 502, 503, 504];

let currentCapability = null;


export async function initToolPage(toolId) {
    renderShell();

    const banner = new ErrorBanner(document.querySelector("#tool-error"));
    const processingHost = document.querySelector("#tool-processing");
    const processing = new ProcessingPanel(processingHost, {
        title: "Processing your file",
    });

    let capability = null;
    try {
        await loadCapabilities();
        capability = getTool(toolId);
        currentCapability = capability;
    } catch {
        capability = null;
    }

    const available = Boolean(
        capability && capability.status === "available"
    );
    if (!available) {
        const unavailableBox = document.querySelector("#tool-unavailable");
        if (unavailableBox) {
            unavailableBox.textContent =
                capability && capability.status === "unavailable"
                    ? "This tool is not available in the current environment."
                    : "This tool is coming soon.";
            showElement(unavailableBox);
        }
        for (const element of document.querySelectorAll(
            "#tool-options button, #tool-options input, #tool-options select, #tool-options textarea, #tool-run"
        )) {
            element.disabled = true;
        }
        // Grey out the upload zone so it no longer looks interactive.
        const uploadHost = document.querySelector("#tool-upload");
        if (uploadHost) {
            uploadHost.classList.add("is-disabled");
            uploadHost.setAttribute("aria-disabled", "true");
        }
    }

    return {
        capability,
        available,
        banner,
        processing,
        setBusy(busy, message) {
            if (busy) {
                if (message) {
                    processing.setMessage(message);
                }
                processing.show();
            } else {
                processing.hide();
            }
        },
        showResult() {
            showResultBox(document.querySelector("#tool-results"));
        },
        showError(error) {
            const status = error && error.status;
            if (status && ERROR_PAGES.includes(Number(status))) {
                const url = `/errors/${Number(status)}.html` +
                    (error.message ? `?detail=${encodeURIComponent(String(error.message))}` : "");
                window.location.href = url;
                return;
            }
            if (error && /offline|network|timed out|failed to fetch|internet connection/i.test(error.message || "")) {
                window.location.href = "/errors/offline.html";
                return;
            }
            banner.show(
                (error && error.message) ||
                    "Something went wrong. Please try again."
            );
        },
    };
}

export function triggerDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
}

export function showResultBox(host) {
    showElement(host);
}


export function setupUpload({ onFiles, extraAccept = "" }) {
    const host = document.querySelector("#tool-upload");
    const accept = (host.dataset.accept || "") + (extraAccept ? "," + extraAccept : "");
    const multiple = host.dataset.multiple === "true";
    const maxFiles = Number(host.dataset.maxFiles || 1);
    const maxSizeMb = (currentCapability && currentCapability.max_upload_mb) || 100;
    // Page hints hardcode the local limits ("up to 25 MB"); show the real one.
    const hint = (host.dataset.hint || "").replace(
        /(\d+)\s*MB/g,
        (text, mb) => (Number(mb) > maxSizeMb ? `${maxSizeMb} MB` : text)
    );
    return new UploadZone(host, {
        accept,
        multiple,
        maxFiles,
        hint,
        // The server's limit, which is far lower on Vercel (4 MB request cap).
        maxSizeMb,
        onFiles,
    });
}


export function renderImageResult(host, result, { originalSize = null } = {}) {
    host.innerHTML = "";
    const grid = document.createElement("div");
    grid.className = "result-grid";

    const preview = document.createElement("div");
    preview.className = "result-preview";

    const img = document.createElement("img");
    img.src = result.download_url;
    img.alt = result.filename;
    img.loading = "lazy";

    const name = document.createElement("div");
    name.className = "result-name";
    name.textContent = result.filename;

    const meta = document.createElement("div");
    meta.className = "result-meta";
    let metaText = `${formatBytes(result.size_bytes)}`;
    if (originalSize !== null && originalSize !== result.size_bytes) {
        metaText = `${formatBytes(originalSize)} → ${metaText}`;
    }
    if (result.details && result.details.width && result.details.height) {
        metaText += ` · ${result.details.width}×${result.details.height}px`;
    }
    meta.textContent = metaText;

    const actions = document.createElement("div");
    actions.className = "result-actions";
    const download = document.createElement("a");
    download.className = "primary-button";
    download.href = result.download_url;
    download.download = result.filename;
    download.textContent = "Download";
    actions.appendChild(download);

    const again = document.createElement("button");
    again.type = "button";
    again.className = "secondary-button";
    again.textContent = "Process another";
    again.addEventListener("click", () => {
        host.innerHTML = "";
        window.scrollTo({ top: 0, behavior: "smooth" });
    });
    actions.appendChild(again);

    preview.appendChild(img);
    preview.appendChild(name);
    preview.appendChild(meta);
    preview.appendChild(actions);
    grid.appendChild(preview);
    host.appendChild(grid);
    showResultBox(host);
    return preview;
}


export function renderFileResult(host, result, { originalSize = null } = {}) {
    host.innerHTML = "";
    const card = createDownloadCard({
        filename: result.filename,
        originalSize,
        resultSize: result.size_bytes,
        downloadUrl: result.download_url,
        label: "Download",
    });
    host.appendChild(card);
    showResultBox(host);
    return card;
}

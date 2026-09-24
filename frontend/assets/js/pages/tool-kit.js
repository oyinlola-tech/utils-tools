import { renderShell } from "../shell.js";
import { loadCapabilities, getTool } from "../capabilities.js";
import {
    ErrorBanner,
    ProcessingPanel,
    UploadZone,
    createDownloadCard,
    setUploadLimit,
} from "../components/ui.js";
import { showElement, formatBytes } from "../utils.js";

// Errors stay on the page: sending people to a separate error page threw
// away the file they chose and every option they had set.
const STATUS_HINTS = {
    408: "The server took too long to answer. Try again, or use a smaller file.",
    413: "The file is too large for the server. Try a smaller file.",
    415: "This file type isn't supported by this tool.",
    429: "Too many requests in a short time. Wait a minute, then try again.",
    500: "The server hit an unexpected error. Try again in a moment.",
    502: "The server is unreachable right now. Try again in a moment.",
    503: "The server is busy. Try again in a moment.",
    504: "The server took too long to answer. Try again, or use a smaller file.",
};


function describeError(error) {
    const message = (error && error.message) || "";
    const status = Number(error && error.status);
    if (/offline|network error|failed to fetch|internet connection/i.test(message)) {
        return navigator.onLine === false
            ? "You're offline. Reconnect, then try again — your file is still selected."
            : "Couldn't reach the server. Check your connection, then try again — your file is still selected.";
    }
    if (status >= 500 || status === 413 || status === 429 || status === 408) {
        const hint = STATUS_HINTS[status] || STATUS_HINTS[500];
        return message && !/unexpected error occurred|request failed/i.test(message)
            ? `${message} ${hint}`
            : hint;
    }
    return message || "Something went wrong. Check the file and your settings, then try again.";
}


export async function initToolPage(toolId) {
    renderShell();

    const banner = new ErrorBanner(document.querySelector("#tool-error"));
    const processingHost = document.querySelector("#tool-processing");
    const processing = new ProcessingPanel(processingHost, {
        title: "Working on it",
    });

    let capability = null;
    try {
        await loadCapabilities();
        capability = getTool(toolId);
    } catch {
        capability = null;
    }
    if (capability && capability.max_upload_mb) {
        setUploadLimit(capability.max_upload_mb);
    }

    const available = Boolean(capability && capability.status === "available");
    if (!available) {
        const unavailableBox = document.querySelector("#tool-unavailable");
        if (unavailableBox) {
            unavailableBox.textContent =
                capability && capability.status === "unavailable"
                    ? "This tool can't run on this server — it needs software that isn't installed here. It works when you run Utils-tool on your own machine."
                    : "This tool is coming soon.";
            showElement(unavailableBox);
        }
        for (const element of document.querySelectorAll(
            "#tool-options button, #tool-options input, #tool-options select, #tool-options textarea, #tool-run"
        )) {
            element.disabled = true;
        }
        const uploadHost = document.querySelector("#tool-upload");
        if (uploadHost) {
            uploadHost.classList.add("is-disabled");
            uploadHost.setAttribute("aria-disabled", "true");
        }
    }

    const run = document.querySelector("#tool-run");

    return {
        capability,
        available,
        banner,
        processing,
        setBusy(busy, message) {
            if (busy) {
                banner.hide();
                if (message) {
                    processing.setMessage(message);
                }
                processing.show();
            } else {
                processing.hide();
            }
            if (run && available) {
                run.disabled = busy;
                run.classList.toggle("is-busy", busy);
            }
        },
        showResult() {
            showResultBox(document.querySelector("#tool-results"));
        },
        showError(error) {
            processing.hide();
            if (run && available) {
                run.disabled = false;
                run.classList.remove("is-busy");
            }
            banner.show(describeError(error));
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
    host.classList.add("is-ready");
    if (!host.dataset.announced) {
        host.dataset.announced = "true";
        host.setAttribute("aria-live", "polite");
    }
    host.scrollIntoView({ behavior: "smooth", block: "nearest" });
}


export function setupUpload({ onFiles, extraAccept = "" }) {
    const host = document.querySelector("#tool-upload");
    const accept = (host.dataset.accept || "") + (extraAccept ? "," + extraAccept : "");
    return new UploadZone(host, {
        accept,
        multiple: host.dataset.multiple === "true",
        maxFiles: Number(host.dataset.maxFiles || 1),
        hint: host.dataset.hint || "",
        maxSizeMb: 100,
        onFiles,
    });
}


function resultHeader(host, title) {
    const header = document.createElement("div");
    header.className = "result-head";
    const heading = document.createElement("p");
    heading.className = "result-title";
    heading.textContent = title;
    const again = document.createElement("button");
    again.type = "button";
    again.className = "result-reset";
    again.textContent = "Clear result";
    again.addEventListener("click", () => {
        host.innerHTML = "";
        host.classList.remove("is-ready");
        const upload = document.querySelector("#tool-upload");
        (upload || document.body).scrollIntoView({ behavior: "smooth", block: "center" });
    });
    header.append(heading, again);
    return header;
}


export function renderImageResult(host, result, { originalSize = null } = {}) {
    host.innerHTML = "";
    host.appendChild(resultHeader(host, "Done — your image is ready."));

    const preview = document.createElement("div");
    preview.className = "result-preview";

    const frame = document.createElement("div");
    frame.className = "result-frame";
    const img = document.createElement("img");
    img.src = result.download_url;
    img.alt = `Preview of ${result.filename}`;
    img.loading = "lazy";
    frame.appendChild(img);

    const body = document.createElement("div");
    body.className = "result-body";

    const name = document.createElement("div");
    name.className = "result-name";
    name.textContent = result.filename;

    const meta = document.createElement("div");
    meta.className = "result-meta";
    const parts = [];
    if (originalSize !== null && originalSize !== result.size_bytes) {
        parts.push(`${formatBytes(originalSize)} → ${formatBytes(result.size_bytes)}`);
    } else {
        parts.push(formatBytes(result.size_bytes));
    }
    if (result.details && result.details.width && result.details.height) {
        parts.push(`${result.details.width}×${result.details.height}px`);
    }
    meta.textContent = parts.join(" · ");

    const actions = document.createElement("div");
    actions.className = "result-actions";
    const download = document.createElement("a");
    download.className = "primary-button";
    download.href = result.download_url;
    download.download = result.filename;
    download.textContent = "Download";
    actions.appendChild(download);

    body.append(name, meta, actions);
    preview.append(frame, body);
    host.appendChild(preview);
    showResultBox(host);
    return preview;
}


export function renderFileResult(host, result, { originalSize = null } = {}) {
    host.innerHTML = "";
    host.appendChild(resultHeader(host, "Done — your file is ready."));
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

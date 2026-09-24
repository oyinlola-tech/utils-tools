import { formatBytes, showElement, hideElement } from "../utils.js";
import { takeFiles } from "../handoff.js";

const MIME_EXTENSION_MAP = {
    "image/": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp", ".svg", ".ico", ".tiff", ".tif"],
    "application/pdf": [".pdf"],
};

const MIME_LABELS = {
    "image/jpeg": "JPG",
    "image/jpg": "JPG",
    "image/png": "PNG",
    "image/webp": "WEBP",
    "image/avif": "AVIF",
    "image/gif": "GIF",
    "image/svg+xml": "SVG",
    "image/*": "IMG",
    "application/pdf": "PDF",
};

// Set by the tool kit from /api/v1/capabilities. On Vercel the server
// rejects request bodies over ~4.5 MB, so the page must never promise more.
let serverUploadLimitMb = null;

export function setUploadLimit(limitMb) {
    serverUploadLimitMb = Number(limitMb) || null;
}

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function extensionOf(name) {
    const match = /\.([a-z0-9]{1,5})$/i.exec(name || "");
    return match ? match[1].toUpperCase() : "FILE";
}

function acceptLabels(acceptList) {
    const labels = [];
    for (const entry of acceptList) {
        const label = entry.startsWith(".")
            ? entry.slice(1).toUpperCase()
            : MIME_LABELS[entry.toLowerCase()];
        if (label && !labels.includes(label)) {
            labels.push(label);
        }
    }
    return labels;
}

function acceptNoun(labels, multiple) {
    const imageLabels = ["JPG", "PNG", "WEBP", "AVIF", "GIF", "IMG"];
    let noun = multiple ? "files" : "a file";
    if (labels.length && labels.every((label) => imageLabels.includes(label))) {
        noun = multiple ? "images" : "an image";
    } else if (labels.length === 1 && labels[0] === "PDF") {
        noun = multiple ? "PDFs" : "a PDF";
    } else if (labels.length === 1 && labels[0] === "SVG") {
        noun = multiple ? "SVG files" : "an SVG file";
    }
    return noun;
}


export class UploadZone {
    constructor(host, options = {}) {
        this.host = host;
        this.options = options;
        this.accept = options.accept || "";
        this.multiple = options.multiple !== false;
        this.maxFiles = this.multiple ? options.maxFiles || 20 : 1;
        const requested = options.maxSizeMb || 100;
        this.maxSizeMb = serverUploadLimitMb
            ? Math.min(requested, serverUploadLimitMb)
            : requested;
        this.onFiles = options.onFiles || (() => {});
        this.onError = options.onError || (() => {});
        // Hints are written for local limits ("up to 25 MB"); show the real one.
        this.hint = (options.hint || "").replace(/(\d+)\s*MB/g, (text, mb) =>
            Number(mb) > this.maxSizeMb ? `${this.maxSizeMb} MB` : text
        );
        this.acceptList = this.accept
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean);
        this.labels = acceptLabels(this.acceptList);
        this.noun = acceptNoun(this.labels, this.multiple);
        this.files = [];
        this.previews = new Map();
        this.render();
        this.wire();
        this.receiveHandoff();
    }

    render() {
        const inputId = `file-input-${Math.random().toString(36).slice(2, 9)}`;
        const sheets = (this.labels.length ? this.labels : ["FILE"]).slice(0, 3);
        this.host.classList.add("upload");
        this.host.innerHTML = `
            <div class="upload-drop" data-upload-drop>
                <div class="upload-sheets" aria-hidden="true">
                    ${sheets
                        .map((label, index) => `<span class="upload-sheet" style="--i:${index}">${escapeHtml(label)}</span>`)
                        .join("")}
                </div>
                <div class="upload-copy">
                    <p class="upload-title">Drop ${escapeHtml(this.noun)} here</p>
                    <p class="upload-sub">
                        <label for="${inputId}" class="upload-browse">Browse your device</label>
                        <span class="upload-or">or paste with <kbd>Ctrl</kbd> <kbd>V</kbd></span>
                    </p>
                    ${this.hint ? `<p class="upload-hint">${escapeHtml(this.hint)}</p>` : ""}
                </div>
                <input id="${inputId}" type="file" ${this.accept ? `accept="${escapeHtml(this.accept)}"` : ""} ${this.multiple ? "multiple" : ""} class="visually-hidden" />
            </div>
            <div class="upload-tray hidden" data-upload-tray>
                <ul class="upload-list" aria-label="Selected files" data-upload-list></ul>
                <div class="upload-tray-bar">
                    <span class="upload-total" data-upload-total aria-live="polite"></span>
                    <span class="upload-tray-actions">
                        <label for="${inputId}" class="upload-action">${this.multiple ? "Add more" : "Replace"}</label>
                        <button type="button" class="upload-action" data-upload-clear>${this.multiple ? "Clear all" : "Remove"}</button>
                    </span>
                </div>
            </div>
            <div class="upload-error hidden" role="alert" data-upload-error></div>`;
        this.dropZone = this.host.querySelector("[data-upload-drop]");
        this.input = this.host.querySelector("input[type=file]");
        this.tray = this.host.querySelector("[data-upload-tray]");
        this.list = this.host.querySelector("[data-upload-list]");
        this.total = this.host.querySelector("[data-upload-total]");
        this.errorEl = this.host.querySelector("[data-upload-error]");
    }

    wire() {
        this.input.addEventListener("change", () => {
            const selected = Array.from(this.input.files || []);
            this.input.value = "";
            this.addFiles(selected);
        });

        // The whole host is a drop target, so files can land on the tray too.
        let depth = 0;
        this.host.addEventListener("dragenter", (event) => {
            if (!Array.from(event.dataTransfer?.types || []).includes("Files")) {
                return;
            }
            event.preventDefault();
            depth += 1;
            this.host.classList.add("is-dragging");
        });
        this.host.addEventListener("dragover", (event) => {
            event.preventDefault();
        });
        this.host.addEventListener("dragleave", () => {
            depth = Math.max(0, depth - 1);
            if (!depth) {
                this.host.classList.remove("is-dragging");
            }
        });
        this.host.addEventListener("drop", (event) => {
            event.preventDefault();
            depth = 0;
            this.host.classList.remove("is-dragging");
            this.addFiles(Array.from(event.dataTransfer.files || []));
        });

        this.dropZone.addEventListener("click", (event) => {
            if (!event.target.closest("label, input, kbd")) {
                this.input.click();
            }
        });

        document.addEventListener("paste", (event) => {
            if (this.host.classList.contains("is-disabled")) {
                return;
            }
            if (event.target.closest && event.target.closest("input, textarea, [contenteditable]")) {
                return;
            }
            const pasted = Array.from(event.clipboardData?.files || []);
            if (pasted.length) {
                event.preventDefault();
                this.addFiles(pasted.map((file, index) => this.namePasted(file, index)));
            }
        });

        this.list.addEventListener("click", (event) => {
            const button = event.target.closest("[data-action]");
            if (!button) {
                return;
            }
            const index = Number(button.closest("[data-index]").dataset.index);
            const action = button.dataset.action;
            if (action === "remove") {
                this.removeAt(index);
            } else if (action === "up" || action === "down") {
                this.move(index, action === "up" ? -1 : 1);
            }
        });

        this.host.querySelector("[data-upload-clear]").addEventListener("click", () => {
            this.setFiles([]);
        });

        this.guardRunButton();
    }

    // Pages only react to non-empty selections, so without this a removed
    // file could still be processed when the user presses Run.
    guardRunButton() {
        if (this.host.id !== "tool-upload") {
            return;
        }
        const run = document.querySelector("#tool-run");
        if (!run) {
            return;
        }
        run.addEventListener(
            "click",
            (event) => {
                if (!this.files.length && !this.host.classList.contains("is-disabled")) {
                    event.stopImmediatePropagation();
                    event.preventDefault();
                    this.showError(`Add ${this.noun} first, then press “${run.textContent.trim()}”.`);
                    this.host.classList.remove("is-nudged");
                    void this.host.offsetWidth;
                    this.host.classList.add("is-nudged");
                    this.dropZone.scrollIntoView({ behavior: "smooth", block: "center" });
                }
            },
            true
        );
    }

    namePasted(file, index) {
        if (file.name && file.name !== "image.png") {
            return file;
        }
        const ext = (file.type.split("/")[1] || "png").replace("jpeg", "jpg");
        const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
        return new File([file], `pasted-${stamp}${index ? `-${index}` : ""}.${ext}`, {
            type: file.type,
        });
    }

    async receiveHandoff() {
        if (this.host.id !== "tool-upload" || this.host.classList.contains("is-disabled")) {
            return;
        }
        const handed = await takeFiles();
        const usable = handed.filter((file) => !this.validate(file));
        if (usable.length) {
            this.addFiles(usable);
        } else if (handed.length) {
            this.showError(`${handed[0].name} can't be used here: ${this.validate(handed[0])}`);
        }
    }

    addFiles(incoming) {
        this.clearError();
        if (!incoming.length || this.host.classList.contains("is-disabled")) {
            return;
        }
        if (!this.multiple) {
            incoming = incoming.slice(0, 1);
        }
        const valid = [];
        const problems = [];
        for (const file of incoming) {
            const error = this.validate(file);
            if (error) {
                problems.push(`${file.name}: ${error}`);
            } else {
                valid.push(file);
            }
        }
        const key = (file) => `${file.name}|${file.size}|${file.lastModified}`;
        let next = this.multiple ? [...this.files] : [];
        for (const file of valid) {
            if (!next.some((existing) => key(existing) === key(file))) {
                next.push(file);
            }
        }
        if (next.length > this.maxFiles) {
            problems.push(`Only the first ${this.maxFiles} files were kept (the limit for this tool).`);
            next = next.slice(0, this.maxFiles);
        }
        if (problems.length) {
            this.showError(problems.slice(0, 3).join(" "));
        }
        if (valid.length) {
            this.setFiles(next);
        }
    }

    removeAt(index) {
        const next = [...this.files];
        next.splice(index, 1);
        this.setFiles(next);
    }

    move(index, step) {
        const target = index + step;
        if (target < 0 || target >= this.files.length) {
            return;
        }
        const next = [...this.files];
        [next[index], next[target]] = [next[target], next[index]];
        this.setFiles(next);
        const button = this.list.querySelector(
            `[data-index="${target}"] [data-action="${step < 0 ? "up" : "down"}"]`
        );
        if (button && !button.disabled) {
            button.focus();
        }
    }

    setFiles(files) {
        for (const [file, url] of this.previews) {
            if (!files.includes(file)) {
                URL.revokeObjectURL(url);
                this.previews.delete(file);
            }
        }
        this.files = files;
        this.renderTray();
        if (files.length) {
            this.clearError();
            this.onFiles([...files]);
        }
    }

    previewUrl(file) {
        if (!file.type.startsWith("image/")) {
            return null;
        }
        if (!this.previews.has(file)) {
            this.previews.set(file, URL.createObjectURL(file));
        }
        return this.previews.get(file);
    }

    renderTray() {
        const count = this.files.length;
        this.host.classList.toggle("has-files", count > 0);
        this.tray.classList.toggle("hidden", count === 0);
        const reorderable = this.multiple && count > 1;
        this.list.innerHTML = this.files
            .map((file, index) => {
                const preview = this.previewUrl(file);
                const ext = extensionOf(file.name);
                return `
                <li class="upload-item" data-index="${index}">
                    ${preview
                        ? `<img class="upload-thumb" src="${preview}" alt="" />`
                        : `<span class="upload-thumb upload-thumb-ext">${escapeHtml(ext)}</span>`}
                    <span class="upload-item-text">
                        <span class="upload-item-name" title="${escapeHtml(file.name)}">${escapeHtml(file.name)}</span>
                        <span class="upload-item-meta">${escapeHtml(ext)} · ${formatBytes(file.size)}</span>
                    </span>
                    <span class="upload-item-actions">
                        ${reorderable
                            ? `<button type="button" class="upload-icon-button" data-action="up" aria-label="Move ${escapeHtml(file.name)} up" ${index === 0 ? "disabled" : ""}>↑</button>
                               <button type="button" class="upload-icon-button" data-action="down" aria-label="Move ${escapeHtml(file.name)} down" ${index === count - 1 ? "disabled" : ""}>↓</button>`
                            : ""}
                        <button type="button" class="upload-icon-button" data-action="remove" aria-label="Remove ${escapeHtml(file.name)}">✕</button>
                    </span>
                </li>`;
            })
            .join("");
        const totalBytes = this.files.reduce((sum, file) => sum + file.size, 0);
        this.total.textContent = count
            ? `${count} ${count === 1 ? "file" : "files"} · ${formatBytes(totalBytes)}${this.multiple ? ` · up to ${this.maxFiles}` : ""}`
            : "";
    }

    validate(file) {
        if (this.acceptList.length) {
            const allowedExt = [];
            const allowedMime = [];
            for (const entry of this.acceptList) {
                if (entry.startsWith(".")) {
                    allowedExt.push(entry.toLowerCase());
                } else if (entry.includes("/")) {
                    allowedMime.push(entry);
                }
            }
            const fileName = file.name.toLowerCase();
            const matchesExtension = allowedExt.some((ext) => fileName.endsWith(ext));
            const matchesMime = allowedMime.some((entry) => {
                if (entry.endsWith("/*")) {
                    return file.type.startsWith(entry.slice(0, -1));
                }
                return file.type === entry;
            });
            let matchesExtensionFallback = false;
            if (!file.type && !matchesExtension) {
                matchesExtensionFallback = allowedMime.some((entry) => {
                    const prefix = entry.endsWith("/*") ? entry.slice(0, -1) : entry;
                    const exts = MIME_EXTENSION_MAP[prefix];
                    return exts ? exts.some((ext) => fileName.endsWith(ext)) : false;
                });
            }
            if (!matchesExtension && !matchesMime && !matchesExtensionFallback) {
                return this.labels.length
                    ? `this tool accepts ${this.labels.join(", ")}.`
                    : "this file type isn't supported.";
            }
        }
        if (file.size <= 0) {
            return "the file is empty.";
        }
        if (file.size > this.maxSizeMb * 1024 * 1024) {
            return `it's ${formatBytes(file.size)}; the limit here is ${this.maxSizeMb} MB.`;
        }
        return null;
    }

    showError(message) {
        this.errorEl.textContent = message;
        showElement(this.errorEl);
        this.onError(message);
    }

    clearError() {
        hideElement(this.errorEl);
    }
}


export class ProcessingPanel {
    constructor(host, options = {}) {
        this.host = host;
        this.title = options.title || "Processing your file";
        this.render();
        this.hide();
    }

    render() {
        this.host.innerHTML = `
            <div class="processing" role="status" aria-live="polite">
                <span class="processing-bar" aria-hidden="true"></span>
                <div class="processing-text">
                    <p class="processing-title">${escapeHtml(this.title)}</p>
                    <p class="processing-message">Preparing your file…</p>
                </div>
            </div>`;
        this.message = this.host.querySelector(".processing-message");
    }

    setMessage(message) {
        if (this.message) {
            this.message.textContent = message;
        }
    }

    show() {
        showElement(this.host);
    }

    hide() {
        hideElement(this.host);
    }
}


export class ErrorBanner {
    constructor(host) {
        this.host = host;
        this.host.classList.add("error-message");
        this.host.setAttribute("role", "alert");
        hideElement(this.host);
    }

    show(message) {
        this.host.textContent = message;
        showElement(this.host);
        this.host.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    hide() {
        hideElement(this.host);
    }
}


function sizeChangeBadge(originalSize, resultSize) {
    if (originalSize == null || resultSize == null || !originalSize) {
        return null;
    }
    const change = Math.round((1 - resultSize / originalSize) * 100);
    const badge = document.createElement("span");
    badge.className = "result-badge";
    if (change > 0) {
        badge.textContent = `−${change}%`;
        badge.dataset.tone = "good";
    } else if (change < 0) {
        badge.textContent = `+${Math.abs(change)}%`;
    } else {
        badge.textContent = "same size";
    }
    return badge;
}


export function createDownloadCard({
    filename,
    originalSize,
    resultSize,
    sizeBytes,
    downloadUrl,
    previewUrl = null,
    label,
}) {
    const finalSize = resultSize != null ? resultSize : sizeBytes;
    const element = document.createElement("div");
    element.className = "completed-file result-card";

    if (previewUrl) {
        const thumb = document.createElement("img");
        thumb.className = "result-thumb";
        thumb.src = previewUrl;
        thumb.alt = "";
        thumb.loading = "lazy";
        element.appendChild(thumb);
    } else {
        const ext = document.createElement("span");
        ext.className = "result-thumb result-thumb-ext";
        ext.textContent = extensionOf(filename);
        element.appendChild(ext);
    }

    const info = document.createElement("div");
    info.className = "completed-file-info";

    const name = document.createElement("strong");
    name.className = "completed-file-name";
    name.textContent = filename;
    name.title = filename;

    const meta = document.createElement("div");
    meta.className = "completed-file-meta";
    if (originalSize != null && finalSize != null) {
        meta.textContent = `${formatBytes(originalSize)} → ${formatBytes(finalSize)}`;
        const badge = sizeChangeBadge(originalSize, finalSize);
        if (badge) {
            meta.appendChild(badge);
        }
    } else if (finalSize != null) {
        meta.textContent = formatBytes(finalSize);
    }

    info.appendChild(name);
    info.appendChild(meta);
    element.appendChild(info);

    const download = document.createElement("a");
    download.className = "completed-file-download";
    download.href = downloadUrl;
    download.download = filename;
    download.textContent = label || "Download";
    element.appendChild(download);

    return element;
}

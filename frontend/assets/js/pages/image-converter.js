import { initToolPage } from "./tool-kit.js";
import { apiUpload } from "../api.js";
import { formatBytes, showElement, hideElement } from "../utils.js";
import { UploadZone } from "../components/ui.js";

const kit = await initToolPage("image-converter");

const FORMAT_INFO = {
    png: "PNG preserves transparency and uses lossless compression. Best for graphics and images with sharp lines.",
    jpg: "JPEG does not support transparency. Transparent areas will be filled with the background color. Best for photographs and smaller files.",
    webp: "WebP offers modern compression with optional transparency. Supports both lossy and lossless modes.",
};

let currentFiles = [];
let selectedFormat = "png";

function $(id) {
    return document.getElementById(id);
}

function updateFormatVisibility() {
    const isJpeg = selectedFormat === "jpg";
    const isWebp = selectedFormat === "webp";

    $("field-quality").classList.toggle("hidden", !isJpeg && !isWebp);
    $("field-lossless").classList.toggle("hidden", !isWebp);
    $("field-background").classList.toggle("hidden", !isJpeg);

    const hint = $("format-info");
    if (hint) {
        hint.textContent = FORMAT_INFO[selectedFormat] || "";
    }
}

function setupFormatSelector() {
    const selector = $("format-selector");
    if (!selector) return;

    selector.addEventListener("change", () => {
        selectedFormat = selector.value;
        updateFormatVisibility();
    });
}

function setupBackgroundPresets() {
    const presetSelect = $("background-preset");
    const colorInput = $("background-color");
    if (!presetSelect || !colorInput) return;

    presetSelect.addEventListener("change", () => {
        if (presetSelect.value === "custom") {
            colorInput.focus();
        } else {
            colorInput.value = presetSelect.value;
        }
    });
    colorInput.addEventListener("input", () => {
        presetSelect.value = "custom";
    });
}

function setupQualitySync() {
    const slider = $("quality-slider");
    const input = $("quality-input");

    slider.addEventListener("input", () => {
        input.value = slider.value;
    });
    input.addEventListener("input", () => {
        slider.value = input.value;
    });
}

function setupUpload() {
    return new UploadZone(document.querySelector("#tool-upload"), {
        accept: "image/jpeg,image/png,image/webp,image/jpg",
        multiple: true,
        maxFiles: 50,
        maxSizeMb: 100,
        hint: "JPG, PNG, WebP up to 100 MB",
        onFiles: (files) => {
            currentFiles = files;
            kit.banner.hide();
            updateFileSummary();
        },
    });
}

function updateFileSummary() {
    const upload = document.querySelector("#tool-upload");
    const hint = upload.querySelector(".file-hint");
    if (currentFiles.length === 0) {
        if (hint) hint.textContent = "JPG, PNG, WebP up to 100 MB";
    } else {
        if (hint) hint.textContent = `${currentFiles.length} image(s) ready`;
    }
}

async function handleConvert() {
    if (!currentFiles.length) {
        kit.banner.show("Choose at least one image first.");
        return;
    }

    kit.banner.hide();

    const fields = {
        output_format: selectedFormat,
        remove_metadata: document.querySelector("#remove-metadata").checked,
    };

    const quality = $("quality-input").value;
    if (quality && (selectedFormat === "jpg" || selectedFormat === "webp")) {
        fields.quality = quality;
    }

    if (selectedFormat === "webp" && document.querySelector("#lossless-webp").checked) {
        fields.lossless = "true";
    }

    const bg = $("background-color").value;
    if (bg) {
        fields.background_color = bg;
    }

    kit.setBusy(true, `Converting ${currentFiles.length} image(s)...`);

    try {
        const result = await apiUpload("/images/convert", {
            files: currentFiles.map((file) => ({ name: "files", file })),
            fields,
        });

        kit.setBusy(false);
        renderBatchResult(result);
    } catch (error) {
        kit.setBusy(false);
        kit.banner.show(error.message);
    }
}

function renderBatchResult(result) {
    const host = $("tool-results");
    host.innerHTML = "";

    const header = document.createElement("div");
    header.className = "result-header";
    header.innerHTML = `
        <h2>${result.successful_files} of ${result.total_files} images converted</h2>
    `;
    host.appendChild(header);

    if (result.successful_files > 0) {
        const grid = document.createElement("div");
        grid.className = "result-grid";

        result.results.forEach((item) => {
            const card = renderConvertResult(item);
            grid.appendChild(card);
        });
        host.appendChild(grid);
    }

    if (result.failed_files > 0 && result.failures) {
        const failSection = document.createElement("div");
        failSection.className = "failed-files";
        result.failures.forEach((failure) => {
            const failItem = document.createElement("div");
            failItem.className = "failed-file-item";
            failItem.textContent = `${failure.filename}: ${failure.error}`;
            failSection.appendChild(failItem);
        });
        host.appendChild(failSection);
    }

    const actions = document.createElement("div");
    actions.className = "result-actions";
    const again = document.createElement("button");
    again.type = "button";
    again.className = "secondary-button";
    again.textContent = "Convert another";
    again.addEventListener("click", () => {
        host.innerHTML = "";
        currentFiles = [];
        updateFileSummary();
        window.scrollTo({ top: 0, behavior: "smooth" });
    });
    actions.appendChild(again);
    host.appendChild(actions);

    kit.showResult();
}

function renderConvertResult(item) {
    const card = document.createElement("div");
    card.className = "completed-file";

    const info = document.createElement("div");
    info.className = "completed-file-info";

    const name = document.createElement("strong");
    name.className = "completed-file-name";
    name.textContent = item.original_filename;
    name.title = item.original_filename;

    const meta = document.createElement("div");
    meta.className = "completed-file-meta";

    const fmtText = document.createElement("div");
    fmtText.className = "completed-file-format";
    fmtText.textContent = `${item.input_format} → ${item.output_format.toUpperCase()}`;
    if (item.details && item.details.flattened) {
        fmtText.textContent += " (transparency flattened)";
    }
    meta.appendChild(fmtText);

    const dimText = document.createElement("div");
    dimText.className = "completed-file-dimensions";
    dimText.textContent = `${item.original_width} × ${item.original_height}`;
    meta.appendChild(dimText);

    const sizeText = document.createElement("div");
    sizeText.className = "completed-file-size";
    const origSize = item.original_size_bytes;
    const newSize = item.size_bytes;
    if (origSize !== newSize) {
        if (newSize > origSize) {
            const pct = Math.round(((newSize / origSize) - 1) * 100);
            sizeText.textContent = `${formatBytes(origSize)} → ${formatBytes(newSize)} (size increased by ${pct}%)`;
        } else {
            const pct = Math.round((1 - newSize / origSize) * 100);
            sizeText.textContent = `${formatBytes(origSize)} → ${formatBytes(newSize)} (size reduced by ${pct}%)`;
        }
    } else {
        sizeText.textContent = `${formatBytes(origSize)} (unchanged)`;
    }
    meta.appendChild(sizeText);

    info.appendChild(name);
    info.appendChild(meta);
    card.appendChild(info);

    const preview = document.createElement("div");
    preview.className = "completed-file-preview";
    const img = document.createElement("img");
    img.src = item.download_url;
    img.alt = item.original_filename;
    img.loading = "lazy";
    preview.appendChild(img);
    card.appendChild(preview);

    const download = document.createElement("a");
    download.className = "completed-file-download";
    download.href = item.download_url;
    download.download = item.output_filename;
    download.textContent = "Download";
    card.appendChild(download);

    return card;
}

function initPage() {
    kit.banner.hide();
    setupFormatSelector();
    setupBackgroundPresets();
    setupQualitySync();
    setupUpload();
    updateFormatVisibility();

    $("tool-run").addEventListener("click", handleConvert);
}

if (kit.available) {
    initPage();
}

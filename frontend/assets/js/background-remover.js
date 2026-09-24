import { startBackgroundRemoval } from "./api.js";
import { hideElement, showElement, formatBytes } from "./utils.js";
import { registerUse } from "./support-popup.js";

const dropZone = document.querySelector("#bg-drop-zone");
const fileInput = document.querySelector("#bg-file-input");
const processing = document.querySelector("#bg-processing");
const result = document.querySelector("#bg-result");
const errorMessage = document.querySelector("#bg-error-message");
const originalPreview = document.querySelector("#original-preview");
const processedPreview = document.querySelector("#processed-preview");
const processedPreviewContainer = document.querySelector("#processed-preview-container");
const comparisonDivider = document.querySelector("#comparison-divider");
const comparisonSlider = document.querySelector("#comparison-slider");
const resultMeta = document.querySelector("#bg-result-meta");
const variantGrid = document.querySelector("#bg-variant-grid");
const newImageButton = document.querySelector("#bg-new-image-button");
const outputSelect = document.querySelector("#bg-output-format");
const processingMessage = document.querySelector("#bg-processing-message");
const processingProgress = document.querySelector("#bg-processing-progress");
const processingCount = document.querySelector("#bg-processing-count");

let originalObjectUrl = null;
let selectedOutputFormat = outputSelect ? outputSelect.value : "webp";
let originalFileSize = 0;
let originalFileName = "";

function setOutputOptionsDisabled(disabled) {
    if (outputSelect) {
        outputSelect.disabled = disabled;
    }
}

if (outputSelect) {
    outputSelect.addEventListener("change", () => {
        selectedOutputFormat = outputSelect.value || "webp";
    });
}

function resetUI() {
    hideElement(processing);
    hideElement(result);
    hideElement(errorMessage);
    const badge = document.querySelector("#bg-success-badge");
    if (badge) hideElement(badge);
    setOutputOptionsDisabled(false);
    dropZone.classList.remove("hidden");
    if (originalObjectUrl) {
        URL.revokeObjectURL(originalObjectUrl);
        originalObjectUrl = null;
    }
    originalPreview.removeAttribute("src");
    processedPreview.removeAttribute("src");
    resultMeta.textContent = "";
    variantGrid.innerHTML = "";
    fileInput.value = "";
    originalFileSize = 0;
    originalFileName = "";
    if (processingProgress) processingProgress.style.width = "0%";
    if (processingCount) processingCount.textContent = "";
    if (processingMessage) processingMessage.textContent = "Preparing your image...";
}

function updateBackgroundProgress(stage) {
    if (processingMessage) processingMessage.textContent = stage;
}

function showError(message) {
    hideElement(processing);
    hideElement(result);
    setOutputOptionsDisabled(false);
    dropZone.classList.remove("hidden");
    errorMessage.textContent = message;
    showElement(errorMessage);
}

function showResult(data) {
    hideElement(dropZone);
    hideElement(processing);
    hideElement(errorMessage);

    const info = data.result || data;
    const originalLabel = info.original_filename || originalFileName;
    resultMeta.textContent = [
        originalLabel,
        `${info.width} × ${info.height}`,
        String(info.format || "").toUpperCase(),
        formatBytes(Number(info.size_bytes || 0)),
    ].filter(Boolean).join(" · ");
    processedPreview.src = info.download_url;
    processedPreview.alt = `Processed image (${info.format})`;

    variantGrid.innerHTML = "";
    const card = document.createElement("div");
    card.className = "variant";
    card.innerHTML = `
        <h3>${String(info.format).toUpperCase()}</h3>
        <div class="variant-size">${formatBytes(Number(info.size_bytes || 0))}</div>
        <p class="variant-description">Transparent background, original resolution.</p>
        <a class="primary-button" href="${info.download_url}" download="${info.filename}">Download ${String(info.format).toUpperCase()}</a>
    `;

    if (originalFileSize > 0 && info.size_bytes) {
        const savings = (1 - Number(info.size_bytes) / originalFileSize) * 100;
        const chip = document.createElement("span");
        chip.className = "variant-savings";
        chip.textContent = savings > 0
            ? `${savings.toFixed(1)}% smaller than original`
            : "Similar size to original";
        card.appendChild(chip);
    }

    variantGrid.appendChild(card);

    comparisonSlider.value = 50;
    updateComparison(50);

    showElement(result);
    const badge = document.querySelector("#bg-success-badge");
    if (badge) showElement(badge);
    
    result.style.animation = "none";
    result.offsetHeight;
    result.style.animation = "fadeIn 400ms ease-out";
    
    try {
        registerUse();
    } catch (e) {
        
    }
}

async function processFile(file) {
    if (!file) {
        return;
    }
    if (!file.type || !file.type.startsWith("image/")) {
        showError("Please choose a valid image file.");
        return;
    }

    hideElement(dropZone);
    hideElement(result);
    hideElement(errorMessage);
    showElement(processing);
    setOutputOptionsDisabled(true);

    updateBackgroundProgress("Preparing your image...");
    originalFileSize = file.size || 0;
    originalFileName = file.name || "";
    if (processingCount) processingCount.textContent = file.name;

    try {
        if (originalObjectUrl) {
            URL.revokeObjectURL(originalObjectUrl);
        }
        originalObjectUrl = URL.createObjectURL(file);
        originalPreview.src = originalObjectUrl;
        originalPreview.alt = file.name || "Original image";

        updateBackgroundProgress("Removing background...");

        const data = await startBackgroundRemoval(file, selectedOutputFormat);
        
        updateBackgroundProgress("Encoding result...");
        showResult(data);
        setOutputOptionsDisabled(false);
        
        updateBackgroundProgress("Complete");
    } catch (error) {
        setOutputOptionsDisabled(false);
        showError(error.message || "Something went wrong while processing the image.");
    }
}

fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    processFile(file);
});

dropZone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropZone.classList.add("dragging");
});

dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragging");
});

dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
    const file = event.dataTransfer.files?.[0];
    processFile(file);
});

newImageButton.addEventListener("click", resetUI);

function updateComparison(value) {
    const percentage = Number(value);
    processedPreviewContainer.style.clipPath = `inset(0 0 0 ${percentage}%)`;
    comparisonDivider.style.left = `${percentage}%`;
}

comparisonSlider.addEventListener("input", () => {
    updateComparison(comparisonSlider.value);
});

updateComparison(50);

window.addEventListener("beforeunload", () => {
    if (originalObjectUrl) {
        try {
            URL.revokeObjectURL(originalObjectUrl);
        } catch (e) {}
        originalObjectUrl = null;
    }
});

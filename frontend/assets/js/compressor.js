import { startImageCompression, cancelJob, getJob } from "./api.js";
import { hideElement, showElement, formatBytes } from "./utils.js";
import { registerUse } from "./support-popup.js";
import { takeFiles } from "./handoff.js";

const show = showElement;
const hide = hideElement;

const dropZone = document.querySelector("#compressor-drop-zone");
const fileInput = document.querySelector("#compressor-file-input");
const workspace = document.querySelector("#compressor-workspace");
const fileQueue = document.querySelector("#file-queue");
const processing = document.querySelector("#compression-processing");
const result = document.querySelector("#compression-result");
const errorMessage = document.querySelector("#compression-error");
const compressButton = document.querySelector("#compress-button");
const clearFilesButton = document.querySelector("#clear-files");
const qualitySlider = document.querySelector("#quality-slider");
const qualityValue = document.querySelector("#quality-value");
const targetSize = document.querySelector("#target-size");
const targetSizePreset = document.querySelector("#target-size-preset");
const stripMetadata = document.querySelector("#strip-metadata");
const advancedFormat = document.querySelector("#advanced-format");
const maxDimension = document.querySelector("#max-dimension");
const originalSize = document.querySelector("#original-size");
const compressedSize = document.querySelector("#compressed-size");
const savingsPercent = document.querySelector("#savings-percent");
const downloadButton = document.querySelector("#compression-download");
const compressAnotherButton = document.querySelector("#compress-another");
const processingMessage = document.querySelector("#processing-message");
const processingProgress = document.querySelector("#processing-progress");
const processingCount = document.querySelector("#processing-count");
const cancelCompressionButton = document.querySelector("#cancel-compression");
const resultMeta = document.querySelector("#compression-result-meta");
const completedFiles = document.querySelector("#completed-files");
// Only the PDF compressor page has a preset picker; the image page
// uses the quality slider instead (and the PDF page has no slider).
const qualityPreset = document.querySelector("#quality-preset");

let files = [];
let selectedQuality = 80;
let activeJobId = null;
let cancelling = false;
let userCancelled = false;
let selectedTargetSize = null;



const ACCEPTED_EXTENSIONS = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/jpg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/webp": [".webp"],
    "image/avif": [".avif"],
    "application/pdf": [".pdf"],
};

// This script serves both the image and PDF compressor pages, so the
// allowed types come from the page's own file input.
function isSupportedFile(file) {
    const extension = "." + file.name.split(".").pop().toLowerCase();
    const accepted = (fileInput?.accept || "image/jpeg,image/png,image/webp")
        .split(",")
        .map((token) => token.trim().toLowerCase())
        .filter(Boolean);
    return accepted.some((token) =>
        token.startsWith(".")
            ? token === extension
            : (ACCEPTED_EXTENSIONS[token] || []).includes(extension)
    );
}

function createFileId(file) {
    return [file.name, file.size, file.lastModified].join("-");
}

async function getImageDimensions(file) {
    if (!file.type.startsWith("image/")) {
        return null;
    }

    return new Promise((resolve) => {
        const url = URL.createObjectURL(file);

        const image = new Image();

        image.onload = () => {
            const dimensions = `${image.naturalWidth} × ${image.naturalHeight}`;

            URL.revokeObjectURL(url);

            resolve(dimensions);
        };

        image.onerror = () => {
            URL.revokeObjectURL(url);

            resolve(null);
        };

        image.src = url;
    });
}

async function addFiles(newFiles) {
    for (const file of newFiles) {
        if (!isSupportedFile(file)) {
            continue;
        }

        const id = createFileId(file);

        const alreadyExists = files.some((item) => item.id === id);

        if (alreadyExists) {
            continue;
        }

        let previewUrl = null;

        previewUrl = URL.createObjectURL(file);

        const dimensions = await getImageDimensions(file);

        files.push({
            id,
            file,
            status: "waiting",
            result: null,
            previewUrl,
            dimensions,
        });
    }

    renderQueue();
}

function removeFile(id) {
    const item = files.find((file) => file.id === id);

    if (item?.previewUrl) {
        URL.revokeObjectURL(item.previewUrl);
    }

    files = files.filter((item) => item.id !== id);

    renderQueue();
}

function clearFiles() {
    for (const item of files) {
        if (item.previewUrl) {
            URL.revokeObjectURL(item.previewUrl);
        }
    }

    files = [];

    fileInput.value = "";

    hide(workspace);

    show(dropZone);
    
    const badge = document.querySelector("#compression-success-badge");
    if (badge) hideElement(badge);
}

function renderQueue() {
    fileQueue.innerHTML = "";

    if (!files.length) {
        hide(workspace);
        show(dropZone);
        return;
    }

    hide(dropZone);
    show(workspace);

    for (const item of files) {
        const element = document.createElement("div");

        element.className = "file-queue-item";

         const statusClass = `status-${item.status}`;

        const preview = document.createElement("div");

        preview.className = "file-preview";

        if (item.previewUrl) {
            const image = document.createElement("img");

            image.src = item.previewUrl;

            image.alt = "";

            preview.appendChild(image);
        } else {
            const genericLabel = document.createElement("span");

            genericLabel.className = "file-preview-pdf";

            genericLabel.textContent = "IMG";

            preview.appendChild(genericLabel);
        }

        const main = document.createElement("div");

        main.className = "file-queue-main";

        const details = document.createElement("div");

        details.className = "file-queue-details";

        const name = document.createElement("strong");

        name.className = "file-queue-name";

        name.textContent = item.file.name;

        name.title = item.file.name;

        const meta = document.createElement("div");

        meta.className = "file-queue-meta";

        const size = document.createElement("span");

        size.textContent = formatBytes(item.file.size);

        meta.appendChild(size);

        if (item.dimensions) {
            const dimensions = document.createElement("span");

            dimensions.textContent = item.dimensions;

            meta.appendChild(dimensions);
        }

        details.appendChild(name);
        details.appendChild(meta);

        main.appendChild(preview);
        main.appendChild(details);

        const status = document.createElement("span");

        status.className = `file-queue-status ${statusClass}`;

        status.textContent = getStatusLabel(item);

        const actions = document.createElement("div");

        actions.className = "file-queue-actions";

        if (item.status === "completed" && item.result?.download_url) {
            const download = document.createElement("a");

            download.className = "file-queue-download";

            download.href = item.result.download_url;

            download.download = item.result.output_filename;

            download.textContent = "Download";

            actions.appendChild(download);
        }

        if (item.status !== "processing") {
            const remove = document.createElement("button");

            remove.type = "button";

            remove.className = "file-queue-remove";

            remove.dataset.fileId = item.id;

            remove.setAttribute("aria-label", `Remove ${item.file.name}`);

            remove.textContent = "×";

            actions.appendChild(remove);
        }

        element.appendChild(main);
        element.appendChild(status);
        element.appendChild(actions);

        fileQueue.appendChild(element);
    }

    document.querySelectorAll(".file-queue-remove").forEach((button) => {
        button.addEventListener("click", () => {
            removeFile(button.dataset.fileId);
        });
    });
}

function getStatusLabel(item) {
    if (item.status === "waiting") {
        return "Ready";
    }

    if (item.status === "processing") {
        return "Compressing";
    }

    if (item.status === "completed") {
        if (item.result) {
            return `Saved ${item.result.savings_percent}%`;
        }

        return "Done";
    }

    if (item.status === "failed") {
        return "Failed";
    }

    return item.status;
}

function syncJobToFiles(job) {
    if (!job.files) {
        return;
    }

    for (const serverFile of job.files) {
        const localFile = files.find((item) => item.file.name === serverFile.filename);

        if (!localFile) {
            continue;
        }

        localFile.status = serverFile.status;

        if (serverFile.status === "completed") {
            localFile.result = {
                output_filename: serverFile.output_filename,
                download_url: serverFile.download_url,
                compressed_size_bytes: serverFile.compressed_size_bytes,
                original_size_bytes: serverFile.original_size_bytes,
                savings_percent: serverFile.savings_percent,

                output_format: serverFile.output_format,
                quality: serverFile.quality,
                compression_preset: serverFile.compression_preset,
                width: serverFile.width,
                height: serverFile.height,

                target_size_bytes: serverFile.target_size_bytes,
                target_achieved: serverFile.target_achieved,
            };
        }

        if (serverFile.status === "failed") {
            localFile.result = {
                error: serverFile.error,
            };
        }
    }
}

function renderFailedFiles(job) {
    const container = document.querySelector("#compression-failed-files");
    if (!container) return;

    container.innerHTML = "";

    const failedFiles = (job.files || []).filter((file) => file.status === "failed");
    if (!failedFiles.length) {
        hide(container);
        return;
    }

    show(container);

    const heading = document.createElement("h3");
    heading.className = "failed-files-heading";
    heading.textContent = `Couldn't compress ${failedFiles.length} file${failedFiles.length === 1 ? "" : "s"}`;

    container.appendChild(heading);

    for (const file of failedFiles) {
        const element = document.createElement("div");
        element.className = "failed-file";

        const name = document.createElement("strong");
        name.className = "failed-file-name";
        name.textContent = file.filename;

        const error = document.createElement("span");
        error.className = "failed-file-error";
        error.textContent = file.error || "Something went wrong.";

        element.appendChild(name);
        element.appendChild(error);

        container.appendChild(element);
    }
}

function renderCompletedFiles(job) {
    if (!completedFiles) return;

    completedFiles.innerHTML = "";

    if (!job.files) return;

    for (const file of job.files) {
        if (file.status !== "completed") {
            continue;
        }

        const element = document.createElement("div");

        element.className = "completed-file";

        element.style.animation = "slideIn 300ms ease-out";

        const info = document.createElement("div");

        info.className = "completed-file-info";

        const name = document.createElement("strong");

        name.className = "completed-file-name";

        name.textContent = file.filename;

        const meta = document.createElement("div");
        meta.className = "completed-file-meta";

        const sizeText = document.createElement("div");
        sizeText.textContent = `${formatBytes(file.original_size_bytes)} → ${formatBytes(file.compressed_size_bytes)}`;
        sizeText.className = "completed-file-size";

        const details = document.createElement("div");
        details.className = "completed-file-details";

        
        const formatSpan = document.createElement("span");
        formatSpan.className = "completed-file-detail";
        formatSpan.textContent = file.output_format ? String(file.output_format).toUpperCase() : "";
        details.appendChild(formatSpan);

        
        if (file.width && file.height) {
            const dimensions = document.createElement("span");
            dimensions.className = "completed-file-detail";
            dimensions.textContent = `${file.width} × ${file.height}`;
            details.appendChild(dimensions);
        }

        
        function getPresetLabel(preset) {
            if (preset === "best_quality") return "Best quality";
            if (preset === "smallest") return "Smallest practical size";
            return "Balanced";
        }

        if (!qualityPreset && file.quality) {
            const quality = document.createElement("span");
            quality.className = "completed-file-detail";
            quality.textContent = `Quality ${file.quality}`;
            details.appendChild(quality);
        } else if (file.compression_preset) {
            const preset = document.createElement("span");
            preset.className = "completed-file-detail";
            preset.textContent = getPresetLabel(file.compression_preset);
            details.appendChild(preset);
        }

        
        if (file.target_size_bytes) {
            const target = document.createElement("span");
            target.className = "completed-file-detail";
            if (file.target_achieved) {
                target.textContent = `Target ${formatBytes(file.target_size_bytes)} reached`;
                target.classList.add("target-reached");
            } else {
                target.textContent = `Target ${formatBytes(file.target_size_bytes)} not reached`;
                target.classList.add("target-not-reached");
            }
            details.appendChild(target);
        }

        info.appendChild(name);
        meta.appendChild(sizeText);
        meta.appendChild(details);
        info.appendChild(meta);

        const download = document.createElement("a");

        download.className = "completed-file-download";

        download.href = file.download_url;

        download.download = file.output_filename;

        download.textContent = "Download";

        element.appendChild(info);

        
        const thumb = document.createElement("div");
        thumb.className = "completed-file-thumb";
        if (files) {
            const local = files.find((f) => f.file.name === file.filename);
            if (local && local.previewUrl) {
                const img = document.createElement("img");
                img.src = local.previewUrl;
                img.alt = `Original ${file.filename}`;
                img.className = "completed-thumb-img";
                thumb.appendChild(img);
                img.style.cursor = "pointer";
                img.addEventListener("click", () => {
                    showComparisonModal(local.previewUrl, file.download_url, file.filename);
                });
            }
        }

        element.appendChild(thumb);
        element.appendChild(download);

        completedFiles.appendChild(element);
    }
}

function showComparisonModal(originalUrl, compressedUrl, filename) {
    const previousActive = document.activeElement;

    const overlay = document.createElement("div");
    overlay.className = "comparison-modal";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-label", `Comparison for ${filename}`);

    const container = document.createElement("div");
    container.className = "comparison-modal-inner";

    const close = document.createElement("button");
    close.className = "comparison-modal-close";
    close.type = "button";
    close.setAttribute("aria-label", "Close comparison");
    close.textContent = "×";
    close.tabIndex = 0;

    const view = document.createElement("div");
    view.className = "comparison-view";

    const origImg = document.createElement("img");
    origImg.src = originalUrl;
    origImg.alt = `Original ${filename}`;
    origImg.className = "comparison-original";

    const procContainer = document.createElement("div");
    procContainer.className = "comparison-processed-container";
    const procImg = document.createElement("img");
    procImg.src = compressedUrl;
    procImg.alt = `Compressed ${filename}`;
    procImg.className = "comparison-processed";
    procContainer.appendChild(procImg);

    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = 0;
    slider.max = 100;
    slider.value = 50;
    slider.className = "comparison-range";
    slider.tabIndex = 0;

    view.appendChild(origImg);
    view.appendChild(procContainer);

    container.appendChild(close);
    container.appendChild(view);
    container.appendChild(slider);
    overlay.appendChild(container);
    document.body.appendChild(overlay);

    function update(v) {
        const percent = Number(v);
        procContainer.style.clipPath = `inset(0 0 0 ${percent}%)`;
    }

    slider.addEventListener("input", (e) => update(e.target.value));

    
    const focusable = [close, slider];
    let lastFocusedIndex = 0;

    function keyHandler(e) {
        if (e.key === "Tab") {
            e.preventDefault();
            
            if (e.shiftKey) {
                lastFocusedIndex = (lastFocusedIndex - 1 + focusable.length) % focusable.length;
            } else {
                lastFocusedIndex = (lastFocusedIndex + 1) % focusable.length;
            }
            focusable[lastFocusedIndex].focus();
        }
        if (e.key === "Escape") {
            closeModal();
        }
    }

    function clickOutside(e) {
        if (e.target === overlay) closeModal();
    }

    function closeModal() {
        document.removeEventListener("keydown", keyHandler);
        overlay.removeEventListener("click", clickOutside);
        if (document.body.contains(overlay)) {
            document.body.removeChild(overlay);
        }
        if (previousActive && previousActive.focus) {
            try {
                previousActive.focus();
            } catch (e) {}
        }
    }

    close.addEventListener("click", closeModal);
    document.addEventListener("keydown", keyHandler);
    overlay.addEventListener("click", clickOutside);

    
    close.focus();

    
    try {
        window.__showComparisonModalForTest = showComparisonModal;
    } catch (e) {}
}

if (qualitySlider) {
    qualitySlider.addEventListener("input", () => {
        selectedQuality = Number(qualitySlider.value);
        if (qualityValue) {
            qualityValue.textContent = String(selectedQuality);
        }
    });
}

if (targetSizePreset) {
    targetSizePreset.addEventListener("change", () => {
        const size = targetSizePreset.value;
        if (size === "custom") {
            selectedTargetSize = null;
            if (targetSize) targetSize.value = "";
            show(document.querySelector("#target-size-custom"));
        } else if (size === "") {
            selectedTargetSize = null;
            if (targetSize) targetSize.value = "";
            hide(document.querySelector("#target-size-custom"));
        } else {
            selectedTargetSize = Number(size);
            if (targetSize) targetSize.value = String(selectedTargetSize);
            hide(document.querySelector("#target-size-custom"));
        }
    });
}

fileInput.addEventListener("change", () => {
    addFiles(Array.from(fileInput.files || []));
    fileInput.value = "";
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
    addFiles(Array.from(event.dataTransfer.files));
});

clearFilesButton.addEventListener("click", clearFiles);

async function waitForJob(jobId, signal) {
    const maxWaitMs = 10 * 60 * 1000;
    const startTime = Date.now();
    let pollFailures = 0;

    while (!signal?.aborted) {
        if (Date.now() - startTime > maxWaitMs) {
            throw new Error("Compression timed out. Please try again with smaller files.");
        }

        let job;
        try {
            job = await getJob(jobId);
            pollFailures = 0;
        } catch (error) {
            // A single failed poll (cold start, network blip) should not
            // abandon a job that is still running on the server.
            pollFailures += 1;
            if (pollFailures >= 4 || error.status === 404) {
                throw error;
            }
            await new Promise((resolve) => setTimeout(resolve, 1000 * pollFailures));
            continue;
        }

        syncJobToFiles(job);

        updateProcessingUI(job);

        renderQueue();

        if (job.status === "completed") {
            renderCompletedFiles(job);
            return job;
        }

        if (job.status === "failed") {
            const failedFile = job.files?.find((f) => f.status === "failed");
            const errorMsg = failedFile?.error || "Compression failed. Please try again.";
            throw new Error(errorMsg);
        }

        if (job.status === "cancelled") {
            throw new Error("Compression was cancelled.");
        }

        if (cancelling || activeJobId !== jobId) {
            throw new Error("Compression was cancelled.");
        }

        await new Promise((resolve) => setTimeout(resolve, 500));
    }

    throw new Error("Compression was cancelled.");
}

function updateProcessingUI(job) {
    const completed = job.completed_files || 0;
    const failed = job.failed_files || 0;
    const total = job.total_files || 0;
    const finished = completed + failed;
    const percentage = total > 0 ? (finished / total) * 100 : 0;

    processingProgress.style.width = `${percentage}%`;
    processingCount.textContent = `${finished} of ${total} completed`;

    const currentFile = job.files?.find(
        (file) => file.status === "processing"
    );
    if (currentFile) {
        processingMessage.textContent = `Compressing ${currentFile.filename}`;
    } else if (job.status === "completed") {
        processingMessage.textContent = "All files have been processed.";
    } else {
        processingMessage.textContent = "Preparing your files...";
    }
}

compressButton.addEventListener("click", async () => {
    if (!files.length || activeJobId) {
        return;
    }
    compressButton.disabled = true;
    hide(workspace);
    hide(result);
    hide(errorMessage);
    const badge = document.querySelector("#compression-success-badge");
    if (badge) hideElement(badge);
    const failedFilesContainer = document.querySelector("#compression-failed-files");
    if (failedFilesContainer) hideElement(failedFilesContainer);
    const reductionValue = document.querySelector("#reduction-value");
    if (reductionValue) reductionValue.style.width = "0%";
    show(processing);

    processingProgress.style.width = "0%";
    processingCount.textContent = `0 of ${files.length} completed`;

    const abortController = new AbortController();

    try {
        const startResult = await startImageCompression({
            files: files.map((item) => item.file),
            outputFormat: advancedFormat ? advancedFormat.value : "auto",
            quality: qualitySlider ? selectedQuality : null,
            compressionPreset: qualityPreset ? qualityPreset.value : "balanced",
            maxDimension: maxDimension ? (maxDimension.value || null) : null,
            targetSize: selectedTargetSize !== null ? selectedTargetSize : (targetSize ? (targetSize.value || null) : null),
            removeMetadata: stripMetadata ? stripMetadata.checked : true,
        });
        activeJobId = startResult.job_id;
        cancelCompressionButton.disabled = false;
        cancelCompressionButton.textContent = "Cancel";

        const job = await waitForJob(
            startResult.job_id,
            abortController.signal
        );

        if (!job.download_url) {
            throw new Error(
                "No downloadable archive was created."
            );
        }

        originalSize.textContent = formatBytes(
            Number(job.original_size_bytes || 0)
        );
        compressedSize.textContent = formatBytes(
            Number(job.compressed_size_bytes || 0)
        );
        const savings =
            Number(job.original_size_bytes || 0) > 0
                ? (1 - (Number(job.compressed_size_bytes || 0) / Number(job.original_size_bytes || 1))) * 100
                : 0;
        savingsPercent.textContent = `${savings.toFixed(2)}%`;

        const failedCount = Number(job.failed_files || 0);
        if (failedCount > 0) {
            resultMeta.textContent = `${job.completed_files} completed · ${failedCount} failed`;
        } else {
            resultMeta.textContent = `${job.completed_files} files compressed`;
        }

        downloadButton.href = job.download_url;
        downloadButton.textContent = "Download all";

        const clampedSavings = Math.max(0, Math.min(100, savings));
        const reductionValue = document.querySelector("#reduction-value");
        const reductionLabel = document.querySelector("#reduction-label");
        const summaryMessage = document.querySelector("#compression-summary-message");
        if (reductionValue) reductionValue.style.width = `${clampedSavings}%`;
        if (reductionLabel) reductionLabel.textContent = `${clampedSavings.toFixed(1)}%`;
        if (summaryMessage) {
            if (savings <= 0) {
                summaryMessage.textContent = "Your files were already well optimized — only a little space could be saved.";
            } else if (failedCount > 0) {
                summaryMessage.textContent = `Compressed ${job.completed_files} file(s) and saved ${savings.toFixed(1)}%. ${failedCount} file(s) failed and are listed below.`;
            } else {
                summaryMessage.textContent = `Your ${job.completed_files} file(s) were compressed, saving ${savings.toFixed(1)}% overall.`;
            }
        }

        renderFailedFiles(job);

        hide(processing);
        show(result);
        const badge = document.querySelector("#compression-success-badge");
        if (badge) {
            showElement(badge);
            badge.textContent = failedCount > 0 ? "Partial" : "Done";
            badge.classList.toggle("partial", failedCount > 0);
        }
        
        result.style.animation = "none";
        result.offsetHeight;
        result.style.animation = "fadeIn 400ms ease-out";
        
        
        try {
            registerUse();
        } catch (e) {
            
        }
    } catch (error) {
        hide(processing);
        show(workspace);
        show(errorMessage);
        errorMessage.classList.toggle("is-info", userCancelled);
        errorMessage.textContent =
            userCancelled
                ? "Compression was cancelled. No files were changed."
                : (error.message || "Compression failed.");
    } finally {
        abortController.abort();
        activeJobId = null;
        cancelling = false;
        userCancelled = false;
        compressButton.disabled = false;
        cancelCompressionButton.disabled = false;
        cancelCompressionButton.textContent = "Cancel";
    }
});

cancelCompressionButton.addEventListener("click", async () => {
    if (!activeJobId || cancelling) {
        return;
    }
    cancelling = true;
    userCancelled = true;
    cancelCompressionButton.disabled = true;
    cancelCompressionButton.textContent = "Cancelling...";

    try {
        await cancelJob(activeJobId);
    } catch (error) {
        console.error(error);
    } finally {
        cancelling = false;
    }
});

compressAnotherButton.addEventListener("click", () => {
    clearFiles();
    hide(result);
    hide(errorMessage);
    errorMessage.classList.remove("is-info");
    const badge = document.querySelector("#compression-success-badge");
    if (badge) hideElement(badge);
    const failedFilesContainer = document.querySelector("#compression-failed-files");
    if (failedFilesContainer) hideElement(failedFilesContainer);
    show(dropZone);
});

// Files handed over from the home page's file inspector.
takeFiles().then((handed) => {
    if (handed.length) {
        addFiles(handed);
    }
});

import { initToolPage } from "./tool-kit.js";
import { apiJsonPost, isInputError } from "../api.js";
import { createDownloadCard } from "../components/ui.js";

const kit = await initToolPage("video-downloader");

const urlInput = document.querySelector("#video-url");
const fetchBtn = document.querySelector("#btn-fetch-info");
const runBtn = document.querySelector("#tool-run");
const previewCard = document.querySelector("#video-preview");
const previewThumb = document.querySelector("#preview-thumb");
const previewTitle = document.querySelector("#preview-title");
const previewMeta = document.querySelector("#preview-meta");
const formatSelect = document.querySelector("#video-format");
const qualitySelect = document.querySelector("#video-quality");
const resultsHost = document.querySelector("#tool-results");

let lastFetchedUrl = "";

async function fetchVideoInfo() {
    const url = urlInput.value.trim();
    if (!url) {
        kit.banner.show("Please enter a valid video link.");
        return;
    }

    kit.banner.hide();
    kit.setBusy(true, "Extracting video info...");

    try {
        const response = await apiJsonPost("/tools/video/info", { url });
        kit.setBusy(false);

        if (response && response.success && response.data) {
            const data = response.data;
            lastFetchedUrl = url;

            if (data.thumbnail) {
                previewThumb.src = data.thumbnail;
                previewThumb.classList.remove("hidden");
            } else {
                previewThumb.classList.add("hidden");
            }

            previewTitle.textContent = data.title || "Video";
            previewMeta.textContent = `${data.platform || "Video"} · ${data.duration_formatted} · ${data.uploader}`;
            previewCard.classList.remove("hidden");

            // Update quality options dynamically if provided
            if (data.available_qualities && data.available_qualities.length > 0) {
                qualitySelect.innerHTML = `<option value="best" selected>Best Available</option>`;
                for (const q of data.available_qualities) {
                    const opt = document.createElement("option");
                    opt.value = q;
                    opt.textContent = q;
                    qualitySelect.appendChild(opt);
                }
            }
        }
    } catch (err) {
        kit.setBusy(false);
        if (isInputError(err)) {
            kit.banner.show(err.message);
        } else {
            kit.showError(err);
        }
    }
}

fetchBtn.addEventListener("click", fetchVideoInfo);

urlInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        fetchVideoInfo();
    }
});

runBtn.addEventListener("click", async () => {
    const url = urlInput.value.trim();
    if (!url) {
        kit.banner.show("Please enter a video link.");
        return;
    }

    kit.banner.hide();
    kit.setBusy(true, "Downloading video without watermark...");

    try {
        const payload = {
            url: url,
            format: formatSelect.value,
            quality: qualitySelect.value,
        };

        const result = await apiJsonPost("/tools/video/download", payload);
        kit.setBusy(false);

        if (result && result.download_url) {
            resultsHost.innerHTML = "";
            const downloadCard = createDownloadCard({
                filename: result.filename,
                resultSize: result.size_bytes,
                downloadUrl: result.download_url,
            });
            resultsHost.appendChild(downloadCard);
            kit.showResult();
        }
    } catch (err) {
        kit.setBusy(false);
        if (isInputError(err)) {
            kit.banner.show(err.message);
        } else {
            kit.showError(err);
        }
    }
});

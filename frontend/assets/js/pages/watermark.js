import { initToolPage, setupUpload, renderImageResult } from "./tool-kit.js";
import { apiUpload } from "../api.js";
import { showElement, hideElement } from "../utils.js";

const kit = await initToolPage("watermark");
if (!kit.available) {
    setupUpload({ onFiles: () => {} });
} else {
    let currentFile = null;
    let logoFile = null;
    setupUpload({
        onFiles: (files) => {
            currentFile = files[0];
        },
    });

    let watermarkType = "text";
    const typeSelect = document.querySelector("#watermark-type");
    typeSelect.addEventListener("change", () => {
        watermarkType = typeSelect.value;
        if (watermarkType === "text") {
            showElement(document.querySelector("#watermark-text-field"));
            hideElement(document.querySelector("#watermark-logo-field"));
        } else {
            hideElement(document.querySelector("#watermark-text-field"));
            showElement(document.querySelector("#watermark-logo-field"));
        }
    });

    document
        .querySelector("#watermark-logo")
        .addEventListener("change", (event) => {
            logoFile = event.target.files[0] || null;
        });

    const bindRange = (id, valueId, suffix = "") => {
        const input = document.querySelector(id);
        const output = document.querySelector(valueId);
        input.addEventListener("input", () => {
            output.textContent = `${input.value}${suffix}`;
        });
    };
    bindRange("#watermark-opacity", "#watermark-opacity-value", "%");
    bindRange("#watermark-size", "#watermark-size-value", "%");
    bindRange("#watermark-rotation", "#watermark-rotation-value", "°");

    document.querySelector("#tool-run").addEventListener("click", async () => {
        if (!currentFile) {
            kit.banner.show("Choose an image first.");
            return;
        }
        if (watermarkType === "logo" && !logoFile) {
            kit.banner.show("Choose a logo image.");
            return;
        }
        kit.banner.hide();
        const fields = {
            position: document.querySelector("#watermark-position").value,
            opacity: document.querySelector("#watermark-opacity").value / 100,
            size_ratio: document.querySelector("#watermark-size").value / 100,
            rotation: document.querySelector("#watermark-rotation").value,
        };
        const files = [{ name: "file", file: currentFile }];
        if (watermarkType === "text") {
            fields.text = document.querySelector("#watermark-text").value;
        } else {
            files.push({ name: "logo", file: logoFile });
        }
        kit.setBusy(true, "Adding watermark...");
        try {
            const result = await apiUpload("/tools/image/watermark", {
                files,
                fields,
            });
            kit.setBusy(false);
            renderImageResult(document.querySelector("#tool-results"), result, {
                originalSize: currentFile.size,
            });
        } catch (error) {
            kit.setBusy(false);
            kit.banner.show(error.message);
        }
    });
}

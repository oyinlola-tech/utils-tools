import { initToolPage, setupUpload, renderFileResult } from "./tool-kit.js";
import { apiUpload, isInputError } from "../api.js";

const kit = await initToolPage("pdf-watermark");
let currentFile = null;

setupUpload({
    onFiles: (files) => {
        currentFile = files[0];
    },
});

document.querySelector("#tool-run").addEventListener("click", async () => {
    if (!currentFile) {
        kit.banner.show("Choose a PDF file first.");
        return;
    }
    const text = document.querySelector("#watermark-text").value.trim();
    if (!text) {
        kit.banner.show("Watermark text cannot be empty.");
        return;
    }
    kit.banner.hide();
    kit.setBusy(true, "Applying watermark...");
    try {
        const result = await apiUpload("/tools/pdf/watermark", {
            files: [{ name: "file", file: currentFile }],
            fields: { text },
        });
        kit.setBusy(false);
        renderFileResult(document.querySelector("#tool-results"), result, {
            originalSize: currentFile.size,
        });
    } catch (err) {
        kit.setBusy(false);
        if (isInputError(err)) {
            kit.banner.show(err.message);
        } else {
            kit.showError(err);
        }
    }
});

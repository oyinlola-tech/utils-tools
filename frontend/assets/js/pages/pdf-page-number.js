import { initToolPage, setupUpload, renderFileResult } from "./tool-kit.js";
import { apiUpload, isInputError } from "../api.js";

const kit = await initToolPage("pdf-page-number");
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
    kit.banner.hide();
    kit.setBusy(true, "Adding page numbers...");
    try {
        const result = await apiUpload("/tools/pdf/page-number", {
            files: [{ name: "file", file: currentFile }],
            fields: { position: document.querySelector("#pdf-position").value },
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

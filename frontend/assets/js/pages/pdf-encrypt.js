import { initToolPage, setupUpload, renderFileResult } from "./tool-kit.js";
import { apiUpload, isInputError } from "../api.js";

const kit = await initToolPage("pdf-encrypt");
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
    const pwd = document.querySelector("#pdf-password").value.trim();
    if (!pwd) {
        kit.banner.show("Enter a password to encrypt the PDF.");
        return;
    }
    kit.banner.hide();
    kit.setBusy(true, "Encrypting PDF...");
    try {
        const result = await apiUpload("/tools/pdf/encrypt", {
            files: [{ name: "file", file: currentFile }],
            fields: { password: pwd },
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

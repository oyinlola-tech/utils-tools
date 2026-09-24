import { initToolPage } from "./tool-kit.js";
import { apiJsonPost } from "../api.js";
import { createDownloadCard } from "../components/ui.js";

const kit = await initToolPage("text-to-speech");

const textInput = document.querySelector("#text-input");
const langSelect = document.querySelector("#tts-lang");
const runBtn = document.querySelector("#tool-run");
const resultsHost = document.querySelector("#tool-results");

runBtn.addEventListener("click", async () => {
    const text = textInput.value.trim();
    if (!text) {
        kit.banner.show("Enter text first.");
        return;
    }

    kit.banner.hide();
    kit.setBusy(true, "Generating speech MP3...");

    try {
        const res = await apiJsonPost("/tools/text/text-to-speech", {
            text: text,
            language: langSelect.value,
        });
        kit.setBusy(false);

        if (res && res.download_url) {
            resultsHost.innerHTML = "";
            const card = createDownloadCard({
                filename: res.filename,
                resultSize: res.size_bytes,
                downloadUrl: res.download_url,
            });
            resultsHost.appendChild(card);
            kit.showResult();
        }
    } catch (err) {
        kit.setBusy(false);
        kit.showError(err);
    }
});

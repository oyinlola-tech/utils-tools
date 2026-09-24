import { initToolPage, setupUpload } from "./tool-kit.js";
import { apiUpload, isInputError } from "../api.js";

const kit = await initToolPage("palette-extractor");
let currentFile = null;

setupUpload({
    onFiles: (files) => {
        currentFile = files[0];
    },
});

const paletteContainer = document.querySelector("#palette-container");

document.querySelector("#tool-run").addEventListener("click", async () => {
    if (!currentFile) {
        kit.banner.show("Choose an image first.");
        return;
    }
    kit.banner.hide();
    kit.setBusy(true, "Extracting color palette...");
    try {
        const res = await apiUpload("/tools/image/palette-extractor", {
            files: [{ name: "file", file: currentFile }],
        });
        kit.setBusy(false);
        if (res && res.colors) {
            paletteContainer.innerHTML = "";
            for (const item of res.colors) {
                const card = document.createElement("div");
                card.className = "color-card";
                card.innerHTML = `
                    <div class="color-swatch" style="background-color: ${item.hex}"></div>
                    <div class="color-info">${item.hex}<br/><span style="font-weight:400;font-size:0.8rem">${item.percentage}%</span></div>
                `;
                paletteContainer.appendChild(card);
            }
            paletteContainer.classList.remove("hidden");
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

import { initToolPage } from "./tool-kit.js";
import { apiJsonPost, isInputError } from "../api.js";

const kit = await initToolPage("case-converter");

const textArea = document.querySelector("#text-input");
const buttons = document.querySelectorAll(".case-buttons button");

buttons.forEach((btn) => {
    btn.addEventListener("click", async () => {
        const text = textArea.value.trim();
        if (!text) {
            kit.banner.show("Enter text first.");
            return;
        }
        const targetCase = btn.getAttribute("data-case");
        kit.banner.hide();
        kit.setBusy(true, "Converting case...");
        try {
            const res = await apiJsonPost("/tools/text/convert-case", {
                text: text,
                target_case: targetCase,
            });
            kit.setBusy(false);
            if (res && res.result) {
                textArea.value = res.result;
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
});

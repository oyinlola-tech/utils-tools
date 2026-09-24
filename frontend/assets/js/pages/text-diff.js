import { initToolPage } from "./tool-kit.js";
import { apiJsonPost, isInputError } from "../api.js";

const kit = await initToolPage("text-diff");

const t1 = document.querySelector("#text-1");
const t2 = document.querySelector("#text-2");
const runBtn = document.querySelector("#tool-run");
const diffBox = document.querySelector("#diff-result");

runBtn.addEventListener("click", async () => {
    kit.banner.hide();
    kit.setBusy(true, "Comparing text...");
    try {
        const res = await apiJsonPost("/tools/text/diff", {
            text1: t1.value,
            text2: t2.value,
        });
        kit.setBusy(false);
        if (res && res.data) {
            diffBox.textContent = res.data.diff || "(No differences found)";
            diffBox.classList.remove("hidden");
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

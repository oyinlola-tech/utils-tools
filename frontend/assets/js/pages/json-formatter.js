import { initToolPage } from "./tool-kit.js";
import { apiJsonPost, isInputError } from "../api.js";

const kit = await initToolPage("json-formatter");

const input = document.querySelector("#json-input");
const output = document.querySelector("#json-output");
const formatBtn = document.querySelector("#btn-format");
const minifyBtn = document.querySelector("#btn-minify");

async function runFormat(minify = false) {
    const text = input.value.trim();
    if (!text) {
        kit.banner.show("Enter JSON text first.");
        return;
    }
    kit.banner.hide();
    kit.setBusy(true, minify ? "Minifying JSON..." : "Formatting JSON...");
    try {
        const res = await apiJsonPost("/tools/dev/json-format", {
            json_text: text,
            minify: minify,
        });
        kit.setBusy(false);
        if (res && res.result) {
            output.value = res.result;
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

formatBtn.addEventListener("click", () => runFormat(false));
minifyBtn.addEventListener("click", () => runFormat(true));

import { initToolPage } from "./tool-kit.js";
import { apiJsonPost, isInputError } from "../api.js";

const kit = await initToolPage("json-csv-converter");

const inputArea = document.querySelector("#input-data");
const outputArea = document.querySelector("#output-data");
const jsonToCsvBtn = document.querySelector("#btn-json-to-csv");
const csvToJsonBtn = document.querySelector("#btn-csv-to-json");

jsonToCsvBtn.addEventListener("click", async () => {
    const val = inputArea.value.trim();
    if (!val) {
        kit.banner.show("Enter JSON input first.");
        return;
    }
    kit.banner.hide();
    kit.setBusy(true, "Converting JSON to CSV...");
    try {
        const res = await apiJsonPost("/tools/dev/json-to-csv", { data: val });
        kit.setBusy(false);
        if (res && res.csv) {
            outputArea.value = res.csv;
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

csvToJsonBtn.addEventListener("click", async () => {
    const val = inputArea.value.trim();
    if (!val) {
        kit.banner.show("Enter CSV input first.");
        return;
    }
    kit.banner.hide();
    kit.setBusy(true, "Converting CSV to JSON...");
    try {
        const res = await apiJsonPost("/tools/dev/csv-to-json", { data: val });
        kit.setBusy(false);
        if (res && res.json) {
            outputArea.value = res.json;
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

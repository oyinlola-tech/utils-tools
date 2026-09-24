import { initToolPage } from "./tool-kit.js";
import { encodeEntities, decodeEntities } from "../devtools/html-entities.js";
import { wireCopy, wireSegmented, debounce, announce } from "../devtools/dom.js";

const kit = await initToolPage("html-entities");

if (kit.available) {
    const input = document.querySelector("#ent-input");
    const output = document.querySelector("#ent-output");
    const style = document.querySelector("#ent-style");
    const inputLabel = document.querySelector("#ent-input-label");
    const outputLabel = document.querySelector("#ent-output-label");

    let mode = "encode";

    function run() {
        output.value = mode === "encode" ? encodeEntities(input.value, { mode: style.value }) : decodeEntities(input.value);
    }

    function setMode(value) {
        mode = value;
        inputLabel.textContent = mode === "encode" ? "Text to encode" : "HTML to decode";
        outputLabel.textContent = mode === "encode" ? "Encoded output" : "Decoded text";
        style.disabled = mode === "decode";
        run();
    }

    const segmented = wireSegmented(document.querySelector("#ent-mode"), setMode);
    input.addEventListener("input", debounce(run, 80));
    style.addEventListener("change", run);
    wireCopy(document.querySelector("#ent-copy"), () => output.value);
    document.querySelector("#ent-swap").addEventListener("click", () => {
        const next = mode === "encode" ? "decode" : "encode";
        input.value = output.value;
        segmented.set(next);
        setMode(next);
        announce(`Switched to ${next}.`);
        input.focus();
    });

    setMode("encode");
}

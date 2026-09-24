import { initToolPage } from "./tool-kit.js";
import { encodeBase64, decodeBase64 } from "../devtools/base64.js";
import { wireCopy, wireSegmented, debounce, announce } from "../devtools/dom.js";

const kit = await initToolPage("base64-encoder");

if (kit.available) {
    const input = document.querySelector("#b64-input");
    const output = document.querySelector("#b64-output");
    const urlSafe = document.querySelector("#b64-urlsafe");
    const inputLabel = document.querySelector("#b64-input-label");
    const outputLabel = document.querySelector("#b64-output-label");
    const meta = document.querySelector("#b64-meta");
    const encoder = new TextEncoder();

    let mode = "encode";

    function run() {
        const text = input.value;
        input.removeAttribute("aria-invalid");
        if (!text) {
            output.value = "";
            meta.textContent = "";
            kit.banner.hide();
            return;
        }
        try {
            if (mode === "encode") {
                output.value = encodeBase64(text, { urlSafe: urlSafe.checked });
                meta.textContent = `${encoder.encode(text).length} UTF-8 bytes → ${output.value.length} Base64 characters`;
            } else {
                output.value = decodeBase64(text);
                meta.textContent = `${encoder.encode(output.value).length} bytes decoded`;
            }
            kit.banner.hide();
        } catch (error) {
            output.value = "";
            meta.textContent = "";
            input.setAttribute("aria-invalid", "true");
            kit.banner.show(error.message);
        }
    }

    function setMode(value) {
        mode = value;
        inputLabel.textContent = mode === "encode" ? "Text to encode" : "Base64 to decode";
        outputLabel.textContent = mode === "encode" ? "Base64 output" : "Decoded text";
        run();
    }

    const segmented = wireSegmented(document.querySelector("#b64-mode"), setMode);

    input.addEventListener("input", debounce(run, 100));
    urlSafe.addEventListener("change", run);
    wireCopy(document.querySelector("#b64-copy"), () => output.value);
    document.querySelector("#b64-swap").addEventListener("click", () => {
        const next = mode === "encode" ? "decode" : "encode";
        input.value = output.value;
        segmented.set(next);
        setMode(next);
        announce(`Switched to ${next}.`);
        input.focus();
    });
    document.querySelector("#b64-clear").addEventListener("click", () => {
        input.value = "";
        run();
        input.focus();
    });

    run();
}

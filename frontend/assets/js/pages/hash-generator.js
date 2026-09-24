import { initToolPage } from "./tool-kit.js";
import { ALGORITHMS, hashAll, encodeDigest } from "../devtools/hash.js";
import { wireCopy, wireSegmented, debounce, keyValueTable, clear } from "../devtools/dom.js";
import { formatBytes } from "../utils.js";

const kit = await initToolPage("hash-generator");

if (kit.available) {
    const textPanel = document.querySelector("#hash-text-panel");
    const filePanel = document.querySelector("#hash-file-panel");
    const textInput = document.querySelector("#hash-text");
    const fileInput = document.querySelector("#hash-file");
    const fileInfo = document.querySelector("#hash-file-info");
    const format = document.querySelector("#hash-format");
    const keyInput = document.querySelector("#hash-key");
    const results = document.querySelector("#hash-results");
    const encoder = new TextEncoder();

    let source = "text";
    let fileBytes = null;
    let digests = null;
    let runId = 0;

    function renderDigests() {
        clear(results);
        if (!digests) {
            return;
        }
        const label = keyInput.value ? "HMAC-" : "";
        const rows = ALGORITHMS.map((algorithm) => [
            `${label}${algorithm}`,
            encodeDigest(digests[algorithm], format.value),
        ]);
        results.appendChild(keyValueTable(rows, { caption: "Hash results" }));
    }

    async function compute() {
        const id = ++runId;
        const bytes = source === "text" ? encoder.encode(textInput.value) : fileBytes;
        if (!bytes) {
            digests = null;
            renderDigests();
            return;
        }
        const key = keyInput.value ? encoder.encode(keyInput.value) : null;
        const large = bytes.length > 20 * 1024 * 1024;
        if (large) {
            kit.setBusy(true, "Hashing file…");
        }
        try {
            const computed = await hashAll(bytes, { key });
            if (id === runId) {
                kit.banner.hide();
                digests = computed;
                renderDigests();
            }
        } catch (error) {
            if (id === runId) {
                kit.banner.show(`Could not compute hashes: ${error.message}`);
            }
        } finally {
            if (large) {
                kit.setBusy(false);
            }
        }
    }

    async function loadFile(file) {
        if (!file) {
            return;
        }
        fileInfo.textContent = `Reading ${file.name}…`;
        try {
            const started = performance.now();
            fileBytes = new Uint8Array(await file.arrayBuffer());
            await compute();
            const seconds = ((performance.now() - started) / 1000).toFixed(2);
            fileInfo.textContent = `${file.name} · ${formatBytes(file.size)} · hashed in ${seconds}s, locally.`;
        } catch {
            fileBytes = null;
            fileInfo.textContent = "That file could not be read. It may be too large for this browser's memory.";
        }
    }

    wireSegmented(document.querySelector("#hash-source"), (value) => {
        source = value;
        textPanel.classList.toggle("hidden", value !== "text");
        filePanel.classList.toggle("hidden", value !== "file");
        (value === "text" ? textInput : fileInput).focus();
        compute();
    });

    const recompute = debounce(compute, 120);
    textInput.addEventListener("input", recompute);
    keyInput.addEventListener("input", recompute);
    format.addEventListener("change", renderDigests);
    fileInput.addEventListener("change", () => loadFile(fileInput.files[0]));
    filePanel.addEventListener("dragover", (event) => {
        event.preventDefault();
    });
    filePanel.addEventListener("drop", (event) => {
        event.preventDefault();
        loadFile(event.dataTransfer.files[0]);
    });

    wireCopy(document.querySelector("#hash-copy-all"), () =>
        digests
            ? ALGORITHMS.map(
                  (algorithm) =>
                      `${keyInput.value ? "HMAC-" : ""}${algorithm}: ${encodeDigest(digests[algorithm], format.value)}`
              ).join("\n")
            : ""
    );

    compute();
}

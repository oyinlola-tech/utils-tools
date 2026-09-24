import { initToolPage } from "./tool-kit.js";
import { encodeUrl, decodeUrl, parseUrl, paramsToObject } from "../devtools/url.js";
import { wireCopy, wireSegmented, debounce, announce, keyValueTable, clear, el, copyButton } from "../devtools/dom.js";

const kit = await initToolPage("url-encoder");

if (kit.available) {
    const input = document.querySelector("#url-input");
    const output = document.querySelector("#url-output");
    const scope = document.querySelector("#url-scope");
    const plus = document.querySelector("#url-plus");
    const plusLabel = plus.closest("label").querySelector(".toggle-label");
    const inputLabel = document.querySelector("#url-input-label");
    const outputLabel = document.querySelector("#url-output-label");
    const parseInput = document.querySelector("#url-parse-input");
    const parseNote = document.querySelector("#url-parse-note");
    const partsHost = document.querySelector("#url-parts");
    const paramsHost = document.querySelector("#url-params");

    let mode = "encode";
    let params = [];

    function convert() {
        input.removeAttribute("aria-invalid");
        try {
            output.value =
                mode === "encode"
                    ? encodeUrl(input.value, { mode: scope.value, spaceAsPlus: plus.checked })
                    : decodeUrl(input.value, { plusAsSpace: plus.checked });
            kit.banner.hide();
        } catch (error) {
            output.value = "";
            input.setAttribute("aria-invalid", "true");
            kit.banner.show(error.message);
        }
    }

    function setMode(value) {
        mode = value;
        inputLabel.textContent = mode === "encode" ? "Text to encode" : "Text to decode";
        outputLabel.textContent = mode === "encode" ? "Encoded output" : "Decoded output";
        plusLabel.textContent = mode === "encode" ? "Use + for spaces (form encoding)" : "Treat + as a space (form encoding)";
        scope.disabled = mode === "decode";
        convert();
    }

    function renderParams() {
        clear(paramsHost);
        if (!params.length) {
            paramsHost.appendChild(el("p", { text: "No query parameters." }));
            return;
        }
        const table = el("table", { className: "analysis-table" }, [
            el("caption", { className: "visually-hidden", text: "Query parameters" }),
            el("thead", {}, [
                el("tr", {}, [
                    el("th", { scope: "col", text: "Parameter" }),
                    el("th", { scope: "col", text: "Value (decoded)" }),
                    el("th", { scope: "col" }, [el("span", { className: "visually-hidden", text: "Actions" })]),
                ]),
            ]),
        ]);
        const body = el("tbody");
        for (const [key, value] of params) {
            body.appendChild(
                el("tr", {}, [
                    el("td", {}, [el("code", { text: key })]),
                    el("td", {}, [el("code", { text: value })]),
                    el("td", {}, [copyButton(() => value, "Copy", `Copy value of ${key}`)]),
                ])
            );
        }
        table.appendChild(body);
        paramsHost.appendChild(table);
    }

    function parse() {
        clear(partsHost);
        parseInput.removeAttribute("aria-invalid");
        if (!parseInput.value.trim()) {
            params = [];
            parseNote.textContent = "Enter a URL to see its parts.";
            clear(paramsHost);
            return;
        }
        try {
            const parts = parseUrl(parseInput.value);
            parseNote.textContent = parts.assumedScheme ? "No scheme given, so https:// was assumed." : "";
            const rows = [
                ["Protocol", parts.protocol],
                ["Origin", parts.origin],
                ["Hostname", parts.hostname],
                ["Port", parts.port || "(default)"],
                ["Path", parts.pathname],
                ["Path (decoded)", parts.decodedPath],
                ["Query string", parts.search],
                ["Fragment", parts.hash],
            ];
            if (parts.username || parts.password) {
                rows.splice(1, 0, ["Username", parts.username], ["Password", parts.password]);
            }
            partsHost.appendChild(keyValueTable(rows, { caption: "URL components" }));
            params = parts.params;
            renderParams();
        } catch (error) {
            params = [];
            parseInput.setAttribute("aria-invalid", "true");
            parseNote.textContent = error.message;
            clear(paramsHost);
        }
    }

    const segmented = wireSegmented(document.querySelector("#url-mode"), setMode);
    input.addEventListener("input", debounce(convert, 100));
    scope.addEventListener("change", convert);
    plus.addEventListener("change", convert);
    parseInput.addEventListener("input", debounce(parse, 150));

    wireCopy(document.querySelector("#url-copy"), () => output.value);
    wireCopy(document.querySelector("#url-params-copy"), () =>
        params.length ? JSON.stringify(paramsToObject(params), null, 2) : ""
    );
    document.querySelector("#url-swap").addEventListener("click", () => {
        const next = mode === "encode" ? "decode" : "encode";
        input.value = output.value;
        segmented.set(next);
        setMode(next);
        announce(`Switched to ${next}.`);
        input.focus();
    });

    setMode("encode");
    parse();
}

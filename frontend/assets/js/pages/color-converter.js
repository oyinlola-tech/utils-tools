import { initToolPage } from "./tool-kit.js";
import { parseColor, formatColor, contrastRatio, wcagResults, toPickerHex } from "../devtools/color.js";
import { debounce, keyValueTable, clear, el } from "../devtools/dom.js";

const kit = await initToolPage("color-converter");

// The canvas parser understands every CSS color the browser does (names,
// lab(), color()), so it backs up the built-in parser.
function createResolver() {
    const context = document.createElement("canvas").getContext("2d");
    if (!context) {
        return null;
    }
    return (text) => {
        context.fillStyle = "#000000";
        context.fillStyle = text;
        const first = context.fillStyle;
        context.fillStyle = "#ffffff";
        context.fillStyle = text;
        return first === context.fillStyle ? first : null;
    };
}

if (kit.available) {
    const resolve = createResolver();
    const input = document.querySelector("#color-input");
    const picker = document.querySelector("#color-picker");
    const swatch = document.querySelector("#color-swatch");
    const note = document.querySelector("#color-note");
    const formatsHost = document.querySelector("#color-formats");
    const fgInput = document.querySelector("#contrast-fg");
    const fgPicker = document.querySelector("#contrast-fg-picker");
    const bgInput = document.querySelector("#contrast-bg");
    const bgPicker = document.querySelector("#contrast-bg-picker");
    const preview = document.querySelector("#contrast-preview");
    const ratioOut = document.querySelector("#contrast-ratio");
    const resultsHost = document.querySelector("#contrast-results");

    let current = null;

    function tryParse(field) {
        try {
            const color = parseColor(field.value, resolve);
            field.removeAttribute("aria-invalid");
            return { color, error: null };
        } catch (error) {
            field.setAttribute("aria-invalid", "true");
            return { color: null, error: error.message };
        }
    }

    function convert() {
        const { color, error } = tryParse(input);
        clear(formatsHost);
        if (!color) {
            note.textContent = error;
            return;
        }
        current = color;
        const formats = formatColor(color);
        swatch.style.background = formats.rgb;
        picker.value = toPickerHex(color);
        note.textContent = color.inGamut
            ? ""
            : "This color is outside the sRGB gamut, so it was clipped to the nearest displayable color.";
        formatsHost.appendChild(
            keyValueTable(
                [
                    ["HEX", formats.hex],
                    ["RGB", formats.rgb],
                    ["HSL", formats.hsl],
                    ["HWB", formats.hwb],
                    ["OKLCH", formats.oklch],
                    ["OKLab", formats.oklab],
                ],
                { caption: "Color formats" }
            )
        );
    }

    function contrast() {
        const fg = tryParse(fgInput);
        const bg = tryParse(bgInput);
        clear(resultsHost);
        if (!fg.color || !bg.color) {
            ratioOut.textContent = "-";
            resultsHost.appendChild(el("p", { text: fg.error || bg.error }));
            return;
        }
        fgPicker.value = toPickerHex(fg.color);
        bgPicker.value = toPickerHex(bg.color);
        preview.style.color = formatColor(fg.color).rgb;
        preview.style.background = formatColor(bg.color).rgb;
        const ratio = contrastRatio(fg.color, bg.color);
        // WCAG says not to round up, so truncate to two decimals.
        ratioOut.textContent = `${(Math.floor(ratio * 100) / 100).toFixed(2)}:1`;
        const list = el("ul");
        for (const result of wcagResults(ratio)) {
            list.appendChild(
                el("li", {}, [
                    el("strong", { text: result.pass ? "Pass" : "Fail" }),
                    ` ${result.label} (needs ${result.threshold}:1)`,
                ])
            );
        }
        resultsHost.appendChild(list);
    }

    input.addEventListener("input", debounce(convert, 120));
    picker.addEventListener("input", () => {
        input.value = picker.value;
        convert();
    });
    for (const [text, colorPicker] of [[fgInput, fgPicker], [bgInput, bgPicker]]) {
        text.addEventListener("input", debounce(contrast, 120));
        colorPicker.addEventListener("input", () => {
            text.value = colorPicker.value;
            contrast();
        });
    }
    document.querySelector("#contrast-swap").addEventListener("click", () => {
        [fgInput.value, bgInput.value] = [bgInput.value, fgInput.value];
        contrast();
    });
    document.querySelector("#contrast-use").addEventListener("click", () => {
        if (current) {
            fgInput.value = formatColor(current).hex;
            contrast();
        }
    });

    convert();
    contrast();
}

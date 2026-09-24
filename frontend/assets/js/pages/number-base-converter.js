import { initToolPage } from "./tool-kit.js";
import { parseInBase, formatInBase, bitLength, twosComplement } from "../devtools/number-base.js";
import { copyButton, debounce, el } from "../devtools/dom.js";

const kit = await initToolPage("number-base-converter");

const GROUP_SIZE = { 2: 4, 8: 3, 10: 3, 16: 4 };
const COPY_NAMES = { 10: "decimal", 16: "hex", 2: "binary", 8: "octal", custom: "custom base" };

if (kit.available) {
    const upper = document.querySelector("#nb-upper");
    const group = document.querySelector("#nb-group");
    const customBase = document.querySelector("#nb-custom-base");
    const info = document.querySelector("#nb-info");
    const fields = [...document.querySelectorAll("input[data-base]")];
    const copyHost = document.querySelector("#nb-copy-actions");
    let value = null;

    for (let base = 2; base <= 36; base += 1) {
        customBase.appendChild(el("option", { value: String(base), text: `Base ${base}` }));
    }
    customBase.value = "36";

    const baseOf = (field) => (field.dataset.base === "custom" ? Number(customBase.value) : Number(field.dataset.base));
    const labelOf = (field) => document.querySelector(`label[for="${field.id}"]`).textContent;

    function render(except = null) {
        for (const field of fields) {
            if (field === except) {
                continue;
            }
            const base = baseOf(field);
            field.value = formatInBase(value, base, {
                uppercase: upper.checked,
                group: group.checked ? GROUP_SIZE[base] || 0 : 0,
            });
            field.removeAttribute("aria-invalid");
        }
        if (value === null) {
            info.textContent = "";
            return;
        }
        const bits = bitLength(value);
        let text = `${bits} bit${bits === 1 ? "" : "s"} · ${Math.ceil(bits / 8)} byte${bits > 8 ? "s" : ""}`;
        if (value < 0n) {
            const width = [8, 16, 32, 64, 128].find((w) => twosComplement(value, w) !== null);
            if (width) {
                text += ` · two's complement (${width}-bit): ${twosComplement(value, width)}`;
            }
        }
        info.textContent = text;
    }

    function onEdit(field) {
        try {
            value = parseInBase(field.value, baseOf(field));
            field.removeAttribute("aria-invalid");
            kit.banner.hide();
            render(field);
        } catch (error) {
            field.setAttribute("aria-invalid", "true");
            kit.banner.show(`${labelOf(field)}: ${error.message}`);
        }
    }

    for (const field of fields) {
        field.addEventListener("input", debounce(() => onEdit(field), 120));
        copyHost.appendChild(
            copyButton(() => field.value, `Copy ${COPY_NAMES[field.dataset.base]}`)
        );
    }
    upper.addEventListener("change", () => render());
    group.addEventListener("change", () => render());
    customBase.addEventListener("change", () => render());

    onEdit(document.querySelector("#nb-10"));
}

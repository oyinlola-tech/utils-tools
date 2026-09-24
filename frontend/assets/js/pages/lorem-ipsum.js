import { initToolPage } from "./tool-kit.js";
import { generateLorem, countStats } from "../devtools/lorem.js";
import { wireCopy, debounce } from "../devtools/dom.js";

const kit = await initToolPage("lorem-ipsum");

const LIMITS = { paragraphs: 200, sentences: 200, words: 5000 };

if (kit.available) {
    const unit = document.querySelector("#lorem-unit");
    const count = document.querySelector("#lorem-count");
    const classic = document.querySelector("#lorem-classic");
    const html = document.querySelector("#lorem-html");
    const output = document.querySelector("#lorem-output");
    const meta = document.querySelector("#lorem-meta");

    function generate() {
        const max = LIMITS[unit.value];
        count.max = String(max);
        const requested = Math.floor(Number(count.value));
        if (!Number.isFinite(requested) || requested < 1 || requested > max) {
            count.setAttribute("aria-invalid", "true");
            kit.banner.show(`Choose between 1 and ${max} ${unit.value}.`);
            return;
        }
        count.removeAttribute("aria-invalid");
        kit.banner.hide();
        output.value = generateLorem({
            unit: unit.value,
            count: requested,
            startWithLorem: classic.checked,
            html: html.checked,
        });
        const stats = countStats(output.value);
        meta.textContent = `${stats.words} words · ${stats.characters} characters`;
    }

    unit.addEventListener("change", generate);
    count.addEventListener("input", debounce(generate, 200));
    classic.addEventListener("change", generate);
    html.addEventListener("change", generate);
    document.querySelector("#lorem-generate").addEventListener("click", generate);
    wireCopy(document.querySelector("#lorem-copy"), () => output.value);

    generate();
}

import { initToolPage } from "./tool-kit.js";
import { parseInput, conversions, listTimeZones } from "../devtools/timestamp.js";
import { wireCopy, debounce, keyValueTable, clear, el } from "../devtools/dom.js";

const kit = await initToolPage("timestamp-converter");

if (kit.available) {
    const input = document.querySelector("#ts-input");
    const unit = document.querySelector("#ts-unit");
    const zone = document.querySelector("#ts-zone");
    const now = document.querySelector("#ts-now");
    const detected = document.querySelector("#ts-detected");
    const resultsHost = document.querySelector("#ts-results");
    let rows = [];

    const localZone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    for (const name of listTimeZones()) {
        zone.appendChild(el("option", { value: name, text: name === localZone ? `${name} (your zone)` : name }));
    }
    if (![...zone.options].some((option) => option.value === localZone)) {
        zone.prepend(el("option", { value: localZone, text: `${localZone} (your zone)` }));
    }
    zone.value = localZone;

    function convert() {
        clear(resultsHost);
        input.removeAttribute("aria-invalid");
        rows = [];
        try {
            const parsed = parseInput(input.value, unit.value);
            rows = conversions(parsed.ms, zone.value);
            detected.textContent =
                parsed.source === "timestamp"
                    ? `Read as a Unix timestamp in ${parsed.unit}.`
                    : "Read as a date string.";
            resultsHost.appendChild(keyValueTable(rows, { caption: "Converted values" }));
            kit.banner.hide();
        } catch (error) {
            detected.textContent = "";
            input.setAttribute("aria-invalid", "true");
            kit.banner.show(error.message);
        }
    }

    function tick() {
        now.textContent = String(Math.floor(Date.now() / 1000));
    }

    input.value = String(Math.floor(Date.now() / 1000));
    input.addEventListener("input", debounce(convert, 150));
    unit.addEventListener("change", convert);
    zone.addEventListener("change", convert);
    document.querySelector("#ts-now-button").addEventListener("click", () => {
        input.value = String(Math.floor(Date.now() / 1000));
        unit.value = "auto";
        convert();
        input.focus();
    });
    wireCopy(document.querySelector("#ts-copy-all"), () =>
        rows.map(([label, value]) => `${label}: ${value}`).join("\n")
    );

    tick();
    setInterval(tick, 1000);
    convert();
}

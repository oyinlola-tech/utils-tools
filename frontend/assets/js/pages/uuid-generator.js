import { initToolPage } from "./tool-kit.js";
import { generateIds, formatId, uuidTimestamp, ulidTimestamp } from "../devtools/uuid.js";
import { wireCopy, debounce } from "../devtools/dom.js";

const kit = await initToolPage("uuid-generator");

if (kit.available) {
    const kind = document.querySelector("#uuid-kind");
    const count = document.querySelector("#uuid-count");
    const upper = document.querySelector("#uuid-upper");
    const hyphens = document.querySelector("#uuid-hyphens");
    const braces = document.querySelector("#uuid-braces");
    const output = document.querySelector("#uuid-output");
    const meta = document.querySelector("#uuid-meta");
    let ids = [];

    const DESCRIPTIONS = {
        v4: "122 random bits each. Use when order does not matter.",
        v7: "Starts with a millisecond timestamp, so IDs sort by creation time. Good for database keys.",
        ulid: "Crockford Base32, 48-bit timestamp + 80 random bits, sortable as plain strings.",
        nil: "All zeros; a placeholder for 'no UUID'.",
    };

    function render() {
        const isUlid = kind.value === "ulid";
        // ULIDs have one canonical (uppercase, unhyphenated) form.
        upper.disabled = isUlid;
        hyphens.disabled = isUlid;
        braces.disabled = isUlid;
        output.value = ids
            .map((id) =>
                isUlid
                    ? id
                    : formatId(id, { uppercase: upper.checked, hyphens: hyphens.checked, braces: braces.checked })
            )
            .join("\n");
        let stamp = null;
        if (ids.length && kind.value === "v7") {
            stamp = uuidTimestamp(ids[0]);
        } else if (ids.length && isUlid) {
            stamp = ulidTimestamp(ids[0]);
        }
        const when = stamp !== null ? ` First ID's embedded time: ${new Date(stamp).toISOString()}.` : "";
        meta.textContent = `${ids.length} ID${ids.length === 1 ? "" : "s"}. ${DESCRIPTIONS[kind.value]}${when}`;
    }

    function generate() {
        const requested = Math.floor(Number(count.value));
        if (!Number.isFinite(requested) || requested < 1 || requested > 1000) {
            count.setAttribute("aria-invalid", "true");
            kit.banner.show("Choose between 1 and 1000 IDs.");
            return;
        }
        count.removeAttribute("aria-invalid");
        kit.banner.hide();
        ids = generateIds({ kind: kind.value, count: requested });
        render();
    }

    kind.addEventListener("change", generate);
    count.addEventListener("input", debounce(generate, 250));
    for (const toggle of [upper, hyphens, braces]) {
        toggle.addEventListener("change", render);
    }
    document.querySelector("#uuid-generate").addEventListener("click", generate);
    wireCopy(document.querySelector("#uuid-copy"), () => output.value);
    generate();
}

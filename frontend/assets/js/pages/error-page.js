import { renderShell } from "../shell.js";

renderShell();

const detailHost = document.querySelector("#error-detail");
if (detailHost) {
    const params = new URLSearchParams(window.location.search);
    let detail = params.get("detail") || "";
    try {
        detail = detail || sessionStorage.getItem("utils-error-detail") || "";
        sessionStorage.removeItem("utils-error-detail");
    } catch {
        // Storage can be blocked; the detail is optional.
    }
    if (detail) {
        detailHost.textContent = detail;
        detailHost.hidden = false;
    }
}

// Render the requested address as a classic hexdump: the same way the
// tools read a file's signature bytes to work out what it is.
function hexdump(text, maxRows = 4) {
    const bytes = new TextEncoder().encode(text);
    const rows = [];
    for (let offset = 0; offset < bytes.length && rows.length < maxRows; offset += 16) {
        const chunk = bytes.slice(offset, offset + 16);
        const hex = Array.from(chunk, (byte) => byte.toString(16).padStart(2, "0"));
        const left = hex.slice(0, 8).join(" ").padEnd(23, " ");
        const right = hex.slice(8).join(" ").padEnd(23, " ");
        const ascii = Array.from(chunk, (byte) =>
            byte >= 32 && byte < 127 ? String.fromCharCode(byte) : "."
        ).join("");
        rows.push({
            offset: offset.toString(16).padStart(4, "0"),
            hex: `${left}  ${right}`,
            ascii,
        });
    }
    const truncated = bytes.length > maxRows * 16;
    return { rows, truncated, length: bytes.length };
}

const dump = document.querySelector("[data-error-dump]");
if (dump) {
    const main = document.querySelector(".error-page");
    const status = main ? main.dataset.status : "";
    const slug = document.querySelector("[data-status-slug]")?.dataset.statusSlug || "";
    const path = decodeURIComponent(window.location.pathname + window.location.search);
    const text = /^\d+$/.test(status) && status !== "404"
        ? `${status} ${slug} ${path}`
        : path;
    const { rows, truncated, length } = hexdump(text);
    dump.textContent = "";
    rows.forEach((row, index) => {
        const line = document.createElement("span");
        line.className = "err-dump-row";
        line.style.setProperty("--row", String(index));
        const offset = document.createElement("span");
        offset.className = "err-dump-offset";
        offset.textContent = row.offset;
        const hex = document.createElement("span");
        hex.className = "err-dump-hex";
        hex.textContent = row.hex;
        const ascii = document.createElement("span");
        ascii.className = "err-dump-ascii";
        ascii.textContent = `|${row.ascii}|`;
        line.append(offset, hex, ascii);
        dump.appendChild(line);
    });
    const end = document.createElement("span");
    end.className = "err-dump-row err-dump-end";
    end.style.setProperty("--row", String(rows.length));
    end.textContent = truncated
        ? `…  ${length} bytes total`
        : `${length.toString(16).padStart(4, "0")}`;
    dump.appendChild(end);
}

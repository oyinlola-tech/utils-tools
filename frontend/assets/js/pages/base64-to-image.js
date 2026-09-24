import { initToolPage, triggerDownload } from "./tool-kit.js";

const kit = await initToolPage("base64-to-image");

function parseBase64(input) {
    let data = input.trim();
    if (!data) {
        throw new Error("Paste some Base64 data first.");
    }
    let mime = null;
    const dataUriMatch = data.match(/^data:([^;,]+);base64,(.+)$/s);
    if (dataUriMatch) {
        mime = dataUriMatch[1];
        data = dataUriMatch[2];
    }
    // Accept URL-safe Base64 and missing padding as well.
    data = data.replace(/\s+/g, "").replace(/-/g, "+").replace(/_/g, "/");
    data = data.replace(/=+$/, "");
    data += "=".repeat((4 - (data.length % 4)) % 4);
    if (!/^[A-Za-z0-9+/]+={0,2}$/.test(data)) {
        throw new Error("This does not look like valid Base64 data.");
    }
    return { data, mime };
}

const SIGNATURES = [
    [[0x89, 0x50, 0x4e, 0x47], "image/png", "png"],
    [[0xff, 0xd8, 0xff], "image/jpeg", "jpg"],
    [[0x47, 0x49, 0x46, 0x38], "image/gif", "gif"],
    [[0x42, 0x4d], "image/bmp", "bmp"],
    [[0x00, 0x00, 0x01, 0x00], "image/x-icon", "ico"],
];

// Raw Base64 (no data: URI) used to be labelled PNG whatever it was.
function sniffType(bytes) {
    for (const [magic, mime, extension] of SIGNATURES) {
        if (magic.every((value, index) => bytes[index] === value)) {
            return { mime, extension };
        }
    }
    const head = String.fromCharCode(...bytes.slice(0, 16));
    if (head.startsWith("RIFF") && head.slice(8, 12) === "WEBP") {
        return { mime: "image/webp", extension: "webp" };
    }
    if (head.slice(4, 12) === "ftypavif") {
        return { mime: "image/avif", extension: "avif" };
    }
    const text = new TextDecoder().decode(bytes.slice(0, 256)).trimStart();
    if (text.startsWith("<svg") || (text.startsWith("<?xml") && text.includes("<svg"))) {
        return { mime: "image/svg+xml", extension: "svg" };
    }
    return null;
}

let previousUrl = null;

async function run() {
    const input = document.querySelector("#base64-input").value;
    kit.banner.hide();
    try {
        const { data, mime } = parseBase64(input);
        const binary = atob(data);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        const sniffed = sniffType(bytes);
        let extension = sniffed ? sniffed.extension : "png";
        let type = (sniffed && sniffed.mime) || mime || "image/png";
        if (!sniffed && mime) {
            const match = mime.match(/^image\/(\w+)/);
            if (match) {
                extension = match[1] === "jpeg" ? "jpg" : match[1];
            }
        }
        const blob = new Blob([bytes], { type });
        if (previousUrl) {
            URL.revokeObjectURL(previousUrl);
        }
        const url = URL.createObjectURL(blob);
        previousUrl = url;
        const host = document.querySelector("#tool-results");
        host.innerHTML = "";
        const preview = document.createElement("div");
        preview.className = "result-preview";
        const img = document.createElement("img");
        img.src = url;
        img.alt = "Decoded image";
        img.addEventListener("error", () => {
            kit.banner.show("The decoded data is not an image this browser can display.");
        });
        const name = document.createElement("div");
        name.className = "result-name";
        name.textContent = `decoded-image.${extension}`;
        const actions = document.createElement("div");
        actions.className = "result-actions";
        const download = document.createElement("button");
        download.type = "button";
        download.className = "primary-button";
        download.textContent = "Download";
        download.addEventListener("click", () =>
            triggerDownload(blob, `decoded-image.${extension}`)
        );
        actions.appendChild(download);
        preview.appendChild(img);
        preview.appendChild(name);
        preview.appendChild(actions);
        host.appendChild(preview);
        kit.showResult();
    } catch (error) {
        kit.banner.show(error.message);
    }
}

document.querySelector("#base64-decode").addEventListener("click", run);

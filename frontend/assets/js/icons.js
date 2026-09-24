const FA_CSS = "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css";

const TOOL_ICONS = {
    "background-remover": "wand-magic-sparkles",
    "background-replacement": "layer-group",
    "image-compressor": "compress",
    "image-converter": "right-left",
    "image-resizer": "expand",
    "image-cropper": "crop",
    "image-editor": "sliders",
    "metadata-remover": "shield-halved",
    watermark: "droplet",
    "pdf-compressor": "file-pdf",
    "pdf-merger": "object-group",
    "pdf-splitter": "scissors",
    "pdf-to-image": "file-image",
    "image-to-pdf": "images",
    "pdf-rotator": "rotate",
    "pdf-extractor": "file-export",
    "file-analyzer": "magnifying-glass",
    "zip-creator": "file-zipper",
    "duplicate-finder": "copy",
    "favicon-generator": "bookmark",
    "svg-optimizer": "vector-square",
    "svg-generator": "bezier-curve",
    "image-to-base64": "binary",
    "base64-to-image": "file-arrow-down",
    "qr-generator": "qrcode",
    "barcode-generator": "barcode",
    "social-media-resizer": "share-nodes",
    "screenshot-beautifier": "window-restore",
};

const CATEGORY_ICONS = {
    image: "image",
    pdf: "file-pdf",
    file: "folder",
    developer: "code",
    text: "font",
    utility: "palette",
};

let injected = false;

export function injectIcons() {
    if (injected) {
        return;
    }
    const existing = document.querySelector('link[data-fa-icons]');
    if (existing) {
        injected = true;
        return;
    }
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = FA_CSS;
    link.setAttribute("data-fa-icons", "true");
    link.media = "print";
    link.onload = () => {
        link.media = "all";
    };
    document.head.appendChild(link);
    injected = true;
}

export function icon(name) {
    const span = document.createElement("span");
    span.className = `fa-solid fa-${name}`;
    span.setAttribute("aria-hidden", "true");
    return span;
}

export function iconHtml(name) {
    return `<span class="fa-solid fa-${name}" aria-hidden="true"></span>`;
}

export function brandIconHtml(name) {
    return `<span class="fa-brands fa-${name}" aria-hidden="true"></span>`;
}

export function toolIconHtml(id) {
    const name = TOOL_ICONS[id] || "wrench";
    return iconHtml(name);
}

export function categoryIconHtml(category) {
    const name = CATEGORY_ICONS[category] || "wrench";
    return iconHtml(name);
}

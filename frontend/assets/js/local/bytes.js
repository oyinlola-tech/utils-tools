/**
 * Byte-level helpers shared by the tools that run in the browser.
 *
 * inspect() mirrors app/shared/file_inspection/file_inspector.py: a file
 * is what its first bytes say it is, never what its name claims.
 */

const CRC_TABLE = new Uint32Array(256);
for (let index = 0; index < 256; index += 1) {
    let value = index;
    for (let bit = 0; bit < 8; bit += 1) {
        value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
    }
    CRC_TABLE[index] = value >>> 0;
}

/** Feed chunks through crc32(bytes, previous) to checksum a stream. */
export function crc32(bytes, previous = 0) {
    let crc = ~previous >>> 0;
    for (let index = 0; index < bytes.length; index += 1) {
        crc = CRC_TABLE[(crc ^ bytes[index]) & 0xff] ^ (crc >>> 8);
    }
    return ~crc >>> 0;
}

export async function sha256Hex(blob) {
    const digest = await crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
    return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join(
        ""
    );
}

export function concat(chunks) {
    const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    const joined = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
        joined.set(chunk, offset);
        offset += chunk.length;
    }
    return joined;
}

const ascii = (text) => Array.from(text, (character) => character.charCodeAt(0));
const startsWith = (bytes, prefix, at = 0) =>
    prefix.every((value, index) => bytes[at + index] === value);

const SIGNATURES = [
    [[0xff, 0xd8, 0xff], "image", "image/jpeg", ".jpg"],
    [[0x89, ...ascii("PNG\r\n"), 0x1a, 0x0a], "image", "image/png", ".png"],
    [ascii("GIF87a"), "image", "image/gif", ".gif"],
    [ascii("GIF89a"), "image", "image/gif", ".gif"],
    [ascii("BM"), "image", "image/bmp", ".bmp"],
    [[...ascii("II*"), 0], "image", "image/tiff", ".tiff"],
    [[...ascii("MM"), 0, 0x2a], "image", "image/tiff", ".tiff"],
    [ascii("%PDF-"), "pdf", "application/pdf", ".pdf"],
];
const UNKNOWN = { category: "unknown", mime_type: "application/octet-stream", extension: "" };
const HEADER_BYTES = 256;

function isAvif(bytes) {
    if (bytes.length < 16 || !startsWith(bytes, ascii("ftyp"), 4)) {
        return false;
    }
    const brand = (at) => String.fromCharCode(...bytes.subarray(at, at + 4));
    if (brand(8) === "avif" || brand(8) === "avis") {
        return true;
    }
    const size = new DataView(bytes.buffer, bytes.byteOffset).getUint32(0);
    const end = Math.min(Math.max(size, 16), bytes.length, HEADER_BYTES);
    for (let at = 16; at + 4 <= end; at += 4) {
        if (brand(at) === "avif" || brand(at) === "avis") {
            return true;
        }
    }
    return false;
}

export async function inspect(file) {
    const bytes = new Uint8Array(await file.slice(0, HEADER_BYTES).arrayBuffer());
    for (const [signature, category, mimeType, extension] of SIGNATURES) {
        if (startsWith(bytes, signature)) {
            return { category, mime_type: mimeType, extension };
        }
    }
    if (bytes.length >= 12 && startsWith(bytes, ascii("RIFF")) && startsWith(bytes, ascii("WEBP"), 8)) {
        return { category: "image", mime_type: "image/webp", extension: ".webp" };
    }
    if (isAvif(bytes)) {
        return { category: "image", mime_type: "image/avif", extension: ".avif" };
    }
    return UNKNOWN;
}

// JPEG start-of-frame markers; C4, C8 and CC share the range but are not frames.
const isFrameMarker = (marker) =>
    marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc;

/**
 * Walks the segments of a JPEG. Yields {marker, start, length} for each
 * segment up to the image data, reading the file a block at a time.
 */
async function* jpegSegments(file) {
    const BLOCK = 64 * 1024;
    let offset = 2;
    while (offset + 4 <= file.size) {
        const head = new DataView(await file.slice(offset, offset + 4).arrayBuffer());
        if (head.getUint8(0) !== 0xff) {
            return;
        }
        const marker = head.getUint8(1);
        if (marker === 0xda || marker === 0xd9) {
            return;
        }
        const length = head.getUint16(2);
        if (length < 2) {
            return;
        }
        const read = (bytes) =>
            file.slice(offset + 4, offset + 4 + Math.min(bytes, length - 2, BLOCK)).arrayBuffer();
        yield { marker, read };
        offset += 2 + length;
    }
}

/**
 * Pixel dimensions as stored, read from the header without decoding.
 * Returns null for formats it does not parse, which the server reports
 * the same way: no dimensions.
 */
export async function storedDimensions(file, mimeType) {
    const view = new DataView(await file.slice(0, 64).arrayBuffer());
    try {
        if (mimeType === "image/png") {
            return { width: view.getUint32(16), height: view.getUint32(20) };
        }
        if (mimeType === "image/gif") {
            return { width: view.getUint16(6, true), height: view.getUint16(8, true) };
        }
        if (mimeType === "image/bmp") {
            return { width: view.getInt32(18, true), height: Math.abs(view.getInt32(22, true)) };
        }
        if (mimeType === "image/webp") {
            const kind = String.fromCharCode(...new Uint8Array(view.buffer, 12, 4));
            if (kind === "VP8 ") {
                return {
                    width: view.getUint16(26, true) & 0x3fff,
                    height: view.getUint16(28, true) & 0x3fff,
                };
            }
            if (kind === "VP8L") {
                const bits = view.getUint32(21, true);
                return { width: (bits & 0x3fff) + 1, height: ((bits >> 14) & 0x3fff) + 1 };
            }
            if (kind === "VP8X") {
                const uint24 = (at) => view.getUint16(at, true) | (view.getUint8(at + 2) << 16);
                return { width: uint24(24) + 1, height: uint24(27) + 1 };
            }
        }
        if (mimeType === "image/jpeg") {
            for await (const { marker, read } of jpegSegments(file)) {
                if (isFrameMarker(marker)) {
                    const frame = new DataView(await read(8));
                    return { width: frame.getUint16(3), height: frame.getUint16(1) };
                }
            }
        }
    } catch {
        // A truncated header has no dimensions to report.
    }
    return null;
}

/** True when a WebP or PNG holds more than one frame. */
export async function isAnimated(file, mimeType) {
    const bytes = new Uint8Array(await file.slice(0, 4096).arrayBuffer());
    if (mimeType === "image/webp") {
        return startsWith(bytes, ascii("VP8X"), 12) && (bytes[20] & 0x02) !== 0;
    }
    if (mimeType === "image/png") {
        const text = String.fromCharCode(...bytes);
        const frames = text.indexOf("acTL");
        const pixels = text.indexOf("IDAT");
        return frames !== -1 && (pixels === -1 || frames < pixels);
    }
    return false;
}

const METADATA_ORDER = ["exif", "gps", "dpi", "icc_profile", "comment", "photoshop"];

/**
 * Which kinds of metadata a file carries, named as Pillow names them.
 * Returns null for formats this does not read.
 */
export async function embeddedMetadata(file, mimeType) {
    const found = new Set();
    const text = (buffer) => String.fromCharCode(...new Uint8Array(buffer));
    try {
        if (mimeType === "image/jpeg") {
            for await (const { marker, read } of jpegSegments(file)) {
                const head = await read(16);
                const label = text(head);
                if (marker === 0xe1 && label.startsWith("Exif")) {
                    // Pillow falls back to the resolution stored in EXIF.
                    found.add("exif").add("dpi");
                } else if (marker === 0xe0 && label.startsWith("JFIF")) {
                    const units = new Uint8Array(head)[7];
                    if (units === 1 || units === 2) {
                        found.add("dpi");
                    }
                } else if (marker === 0xe2 && label.startsWith("ICC_PROFILE")) {
                    found.add("icc_profile");
                } else if (marker === 0xed && label.startsWith("Photoshop")) {
                    found.add("photoshop");
                } else if (marker === 0xfe) {
                    found.add("comment");
                }
            }
        } else if (mimeType === "image/png") {
            let offset = 8;
            while (offset + 12 <= file.size) {
                const head = await file.slice(offset, offset + 32).arrayBuffer();
                const length = new DataView(head).getUint32(0);
                const type = text(head.slice(4, 8));
                const data = new Uint8Array(head, 8);
                if (type === "IDAT" || type === "IEND") {
                    break;
                }
                if (type === "pHYs" && data[8] === 1) {
                    found.add("dpi");
                } else if (type === "iCCP") {
                    found.add("icc_profile");
                } else if (type === "eXIf") {
                    found.add("exif");
                } else if (/^(tEXt|zTXt|iTXt)$/.test(type) && text(data).startsWith("comment\0")) {
                    found.add("comment");
                }
                offset += 12 + length;
            }
        } else if (mimeType === "image/webp") {
            const bytes = new Uint8Array(await file.slice(0, 32).arrayBuffer());
            if (startsWith(bytes, ascii("VP8X"), 12)) {
                if (bytes[20] & 0x08) {
                    found.add("exif");
                }
                if (bytes[20] & 0x20) {
                    found.add("icc_profile");
                }
            }
        } else {
            return null;
        }
    } catch {
        return null;
    }
    return METADATA_ORDER.filter((name) => found.has(name));
}

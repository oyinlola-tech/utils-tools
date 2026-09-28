/**
 * ZIP archives built in the browser.
 *
 * Packaging files on the server meant uploading every one of them only
 * to download them again. Entries are deflated with the browser's own
 * CompressionStream and named by the rules of
 * app/infrastructure/archive/zip_adapter.py.
 */
import { crc32 } from "./bytes.js";

const LOCAL_HEADER = 0x04034b50;
const CENTRAL_HEADER = 0x02014b50;
const END_OF_DIRECTORY = 0x06054b50;
const VERSION = 20;
const UTF8_NAMES = 0x0800;
const DEFLATE = 8;
// Beyond these the format needs ZIP64 records, which are not written here.
const MAX_BYTES = 0xffffffff;
const MAX_ENTRIES = 0xffff;

function entryName(file, used) {
    const name = file.name.replace(/\\/g, "/").split("/").pop();
    if (!name || name === "." || name === "..") {
        return null;
    }
    const dot = name.lastIndexOf(".");
    const stem = dot === -1 ? name : name.slice(0, dot);
    const suffix = dot === -1 ? "" : name.slice(dot);
    let candidate = name;
    for (let copy = 2; used.has(candidate.toLowerCase()); copy += 1) {
        candidate = `${stem} (${copy})${suffix}`;
    }
    used.add(candidate.toLowerCase());
    return candidate;
}

function dosDateTime(timestamp) {
    const date = new Date(timestamp || Date.now());
    const year = Math.max(date.getFullYear(), 1980);
    return {
        time: (date.getHours() << 11) | (date.getMinutes() << 5) | (date.getSeconds() >> 1),
        date: ((year - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate(),
    };
}

/** Deflates a file, checksumming the original bytes as they pass. */
async function deflate(file) {
    let checksum = 0;
    const checked = new TransformStream({
        transform(chunk, controller) {
            checksum = crc32(chunk, checksum);
            controller.enqueue(chunk);
        },
    });
    const compressed = file
        .stream()
        .pipeThrough(checked)
        .pipeThrough(new CompressionStream("deflate-raw"));
    const data = await new Response(compressed).blob();
    return { data, checksum };
}

function header(signature, entry, extra) {
    const name = entry.name;
    const bytes = new Uint8Array((extra ? 46 : 30) + name.length);
    const view = new DataView(bytes.buffer);
    let at = 0;
    const put16 = (value) => {
        view.setUint16(at, value, true);
        at += 2;
    };
    const put32 = (value) => {
        view.setUint32(at, value, true);
        at += 4;
    };
    put32(signature);
    if (extra) {
        put16(VERSION);
    }
    put16(VERSION);
    put16(UTF8_NAMES);
    put16(DEFLATE);
    put16(entry.time);
    put16(entry.date);
    put32(entry.checksum);
    put32(entry.data.size);
    put32(entry.size);
    put16(name.length);
    put16(0);
    if (extra) {
        put16(0); // comment length
        put16(0); // disk number
        put16(0); // internal attributes
        put32(0); // external attributes
        put32(entry.offset);
    }
    bytes.set(name, at);
    return bytes;
}

/**
 * Returns the archive as a Blob, or null when these files need the
 * server: an unsupported browser, a name the server would refuse, or
 * more data than a plain ZIP can describe.
 */
export async function createZip(files) {
    if (typeof CompressionStream !== "function" || !files.length || files.length > MAX_ENTRIES) {
        return null;
    }
    try {
        new CompressionStream("deflate-raw");
    } catch {
        return null;
    }

    const encoder = new TextEncoder();
    const used = new Set();
    const entries = [];
    const parts = [];
    let offset = 0;
    for (const file of files) {
        const name = entryName(file, used);
        if (name === null) {
            return null;
        }
        const entry = {
            name: encoder.encode(name),
            size: file.size,
            offset,
            ...dosDateTime(file.lastModified),
            ...(await deflate(file)),
        };
        const head = header(LOCAL_HEADER, entry, false);
        parts.push(head, entry.data);
        offset += head.length + entry.data.size;
        if (offset > MAX_BYTES) {
            return null;
        }
        entries.push(entry);
    }

    const directory = entries.map((entry) => header(CENTRAL_HEADER, entry, true));
    const directorySize = directory.reduce((sum, record) => sum + record.length, 0);
    const end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, END_OF_DIRECTORY, true);
    end.setUint16(8, entries.length, true);
    end.setUint16(10, entries.length, true);
    end.setUint32(12, directorySize, true);
    end.setUint32(16, offset, true);
    return new Blob([...parts, ...directory, end], { type: "application/zip" });
}

export async function zipTool(files) {
    const archive = await createZip(files);
    if (!archive) {
        return null;
    }
    const first = files[0].name.replace(/\\/g, "/").split("/").pop();
    const stem = first.includes(".") ? first.slice(0, first.lastIndexOf(".")) : first;
    return {
        success: true,
        filename: `${stem}-archive.zip`,
        size_bytes: archive.size,
        download_url: URL.createObjectURL(archive),
        details: { file_count: files.length },
    };
}

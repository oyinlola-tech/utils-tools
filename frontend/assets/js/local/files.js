/**
 * The file analyzer and duplicate finder, computed in the browser.
 *
 * Both only ever read the files, so there is nothing the server adds
 * except the wait for the upload. They answer in the shape of
 * app/modules/file_tools/file_tool_service.py.
 */
import { inspect, sha256Hex, storedDimensions } from "./bytes.js";

// Counting the pages of a PDF or sizing a TIFF needs a parser the
// browser does not have, so batches containing either go to the server.
const NEEDS_SERVER = new Set(["application/pdf", "image/tiff", "image/avif"]);

export async function analyzeTool(files) {
    if (!crypto.subtle) {
        return null;
    }
    const analyzed = [];
    for (const file of files) {
        if (!file.size) {
            return null;
        }
        const kind = await inspect(file);
        if (NEEDS_SERVER.has(kind.mime_type)) {
            return null;
        }
        const entry = {
            filename: file.name,
            size_bytes: file.size,
            ...kind,
            sha256: await sha256Hex(file),
            width: null,
            height: null,
            page_count: null,
        };
        if (kind.category === "image") {
            Object.assign(entry, await storedDimensions(file, kind.mime_type));
        }
        analyzed.push(entry);
    }
    return { success: true, files: analyzed };
}

export async function duplicatesTool(files) {
    if (!crypto.subtle) {
        return null;
    }
    if (files.some((file) => !file.size)) {
        return null;
    }
    const sizes = new Map();
    for (const file of files) {
        sizes.set(file.size, (sizes.get(file.size) || 0) + 1);
    }
    const groups = new Map();
    for (const file of files) {
        // Only files of the same size can be copies of each other.
        if (sizes.get(file.size) < 2) {
            continue;
        }
        const hash = await sha256Hex(file);
        if (!groups.has(hash)) {
            groups.set(hash, { hash, filenames: [], size_bytes: file.size });
        }
        groups.get(hash).filenames.push(file.name);
    }
    return [...groups.values()].filter((group) => group.filenames.length > 1);
}

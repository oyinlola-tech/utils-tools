/**
 * Tools that run in the browser instead of on the server.
 *
 * Each entry answers in the shape of the API response it stands in for,
 * with download links that point at data held in the page. A tool
 * returns null to decline (a format or option it does not handle, a
 * browser missing a feature) and the request is then sent to the server
 * as if this module did not exist.
 */
const TOOLS = {
    "/tools/file/zip": () => import("./zip.js").then((module) => module.zipTool),
    "/tools/file/analyze": () => import("./files.js").then((module) => module.analyzeTool),
    "/tools/file/duplicates": () => import("./files.js").then((module) => module.duplicatesTool),
    "/images/convert": () => import("./images.js").then((module) => module.convertTool),
    "/images/resize": () => import("./images.js").then((module) => module.resizeTool),
    "/tools/image/resize": () => import("./images.js").then((module) => module.presetTool),
    "/tools/image/remove-metadata": () =>
        import("./images.js").then((module) => module.metadataTool),
};

// Tools that work on a reduced copy anyway: the palette is taken from a
// 150 pixel thumbnail and the largest favicon is 512 pixels. The longest
// side uploaded, in pixels.
const UPLOAD_SIDE = {
    "/tools/image/palette-extractor": 600,
    "/tools/dev/favicon": 1024,
};

const fileOf = (entry) => (entry instanceof File ? entry : entry.file);

export async function runLocally(path, entries, fields) {
    const load = TOOLS[path];
    if (!load || !entries.length) {
        return null;
    }
    const tool = await load();
    return tool(entries.map(fileOf), fields);
}

/** Returns the entries to upload, images reduced where that loses nothing. */
export async function prepareUpload(path, entries) {
    const side = UPLOAD_SIDE[path];
    if (!side) {
        return entries;
    }
    const { shrink } = await import("./images.js");
    return Promise.all(
        entries.map(async (entry) => {
            const file = await shrink(fileOf(entry), side);
            return entry instanceof File ? file : { ...entry, file };
        })
    );
}

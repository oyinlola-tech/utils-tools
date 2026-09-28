/**
 * Image conversion and resizing in the browser.
 *
 * A phone photo takes a moment to process and, on a slow connection, a
 * minute to upload; doing the work where the file already is removes the
 * upload. The rules follow app/modules/image/services. Every function
 * here returns null for anything it cannot do exactly as the server
 * would, and the request then goes to the server as before.
 */
import { embeddedMetadata, inspect, isAnimated } from "./bytes.js";
import { canEncodePng, encodePng } from "./png.js";

// The largest canvas every browser allocates, iOS Safari being the
// smallest. It holds a 16 megapixel photo.
const MAX_PIXELS = 16_700_000;
// The server's limits, from app/core/config.py.
const MAX_SIDE = 8000;

const INPUTS = { "image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP" };
const MIME = { jpg: "image/jpeg", png: "image/png", webp: "image/webp" };
const DEFAULT_QUALITY = { jpg: 90, webp: 95 };

// 2x1 pixels, stored with EXIF orientation 6: a browser that applies
// orientation decodes it as 1x2.
const ROTATED_SAMPLE =
    "/9j/4AAQSkZJRgABAQAAAQABAAD/4QAiRXhpZgAATU0AKgAAAAgAAQESAAMAAAABAAYAAAAAAAD/2wBDABALDA4MChAODQ4SERATGCgaGBYWGDEjJR0oOjM9PDkzODdASFxOQERXRTc4UG1RV19iZ2hnPk1xeXBkeFxlZ2P/2wBDARESEhgVGC8aGi9jQjhCY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2NjY2P/wAARCAABAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD0CiiigD//2Q==";

let support = null;

/** Checked once: what this browser decodes correctly and can encode. */
function browserSupport() {
    if (!support) {
        support = (async () => {
            if (typeof createImageBitmap !== "function") {
                return { decode: false };
            }
            const sample = Uint8Array.from(atob(ROTATED_SAMPLE), (c) => c.charCodeAt(0));
            const bitmap = await decode(new Blob([sample], { type: "image/jpeg" }));
            const canvas = newCanvas(1, 1);
            const encodes = async (type) => {
                const blob = await toBlob(canvas, type, 0.9).catch(() => null);
                return Boolean(blob && blob.type === type);
            };
            return {
                decode: bitmap.width === 1 && bitmap.height === 2,
                jpg: await encodes(MIME.jpg),
                webp: await encodes(MIME.webp),
                png: canEncodePng(),
            };
        })().catch(() => ({ decode: false }));
    }
    return support;
}

function decode(blob) {
    return createImageBitmap(blob, { imageOrientation: "from-image" });
}

function newCanvas(width, height) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    return canvas;
}

function toBlob(canvas, type, quality) {
    return new Promise((resolve, reject) => {
        canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("encoding failed"))), type, quality);
    });
}

function context(canvas) {
    const drawing = canvas.getContext("2d", { willReadFrequently: true });
    drawing.imageSmoothingEnabled = true;
    drawing.imageSmoothingQuality = "high";
    return drawing;
}

/**
 * Draws `source` (cropped to `crop`) at the target size. Shrinking by
 * more than half in one step skips source pixels and aliases, so large
 * reductions are taken in halves first.
 */
function draw(source, crop, width, height) {
    let from = source;
    let { x, y, w, h } = crop;
    while (w / 2 >= width && h / 2 >= height) {
        const half = newCanvas(Math.ceil(w / 2), Math.ceil(h / 2));
        context(half).drawImage(from, x, y, w, h, 0, 0, half.width, half.height);
        from = half;
        x = 0;
        y = 0;
        w = half.width;
        h = half.height;
    }
    const canvas = newCanvas(width, height);
    context(canvas).drawImage(from, x, y, w, h, 0, 0, width, height);
    return canvas;
}

function hasTransparency(canvas) {
    const { data } = context(canvas).getImageData(0, 0, canvas.width, canvas.height);
    for (let index = 3; index < data.length; index += 4) {
        if (data[index] !== 255) {
            return true;
        }
    }
    return false;
}

function parseColor(color) {
    if (color === undefined || color === null || color === "") {
        return "#ffffff";
    }
    const cleaned = String(color).replace(/^#/, "").toLowerCase();
    return /^[0-9a-f]{6}$/.test(cleaned) ? `#${cleaned}` : null;
}

/** undefined when not given: the default then depends on the output format. */
function parseQuality(value) {
    if (value === undefined || value === null || value === "") {
        return undefined;
    }
    const quality = Number(value);
    return Number.isInteger(quality) && quality >= 1 && quality <= 100 ? quality : null;
}

const isTrue = (value) => value === true || value === "true";
const isFalse = (value) => value === false || value === "false";

/** Python's round(): halves go to the even neighbour. */
function round(value) {
    const floor = Math.floor(value);
    const fraction = value - floor;
    if (fraction !== 0.5) {
        return Math.round(value);
    }
    return floor % 2 === 0 ? floor : floor + 1;
}

const optionalInt = (value) => {
    if (value === undefined || value === null || value === "") {
        return undefined;
    }
    const number = Number(value);
    return Number.isInteger(number) ? number : NaN;
};

/**
 * app/modules/image/services/resize_math.py. Returns null for input the
 * server rejects, so that the server gets to say why.
 */
function newSize(source, options) {
    const { mode, percent, maxDimension, upscale } = options;
    const { width, height } = options;
    const values = [width, height, maxDimension].filter((value) => value !== undefined);
    if (values.some((value) => !(value > 0)) || [width, height].some((value) => value > MAX_SIDE)) {
        return null;
    }
    if (maxDimension > MAX_SIDE) {
        return null;
    }
    const bounded = (value, limit) => (upscale ? value : Math.min(value, limit));

    if (mode === "percent" && percent !== undefined) {
        if (!(percent > 0) || percent > 10000) {
            return null;
        }
        return {
            width: bounded(Math.max(1, round((source.width * percent) / 100)), source.width),
            height: bounded(Math.max(1, round((source.height * percent) / 100)), source.height),
        };
    }
    if (mode === "max" && maxDimension !== undefined) {
        let ratio = Math.min(maxDimension / source.width, maxDimension / source.height);
        if (!upscale) {
            ratio = Math.min(ratio, 1);
        }
        return {
            width: Math.max(1, round(source.width * ratio)),
            height: Math.max(1, round(source.height * ratio)),
        };
    }
    if ((mode === "exact" || mode === "aspect") && width !== undefined && height !== undefined) {
        return { width, height };
    }
    if (mode === "aspect" && width !== undefined) {
        const scaled = Math.max(1, round(source.height * (width / source.width)));
        return { width: bounded(width, source.width), height: bounded(scaled, source.height) };
    }
    if (mode === "aspect" && height !== undefined) {
        const scaled = Math.max(1, round(source.width * (height / source.height)));
        return { width: bounded(scaled, source.width), height: bounded(height, source.height) };
    }
    return null;
}

/** The largest centered region of the source with the target's shape. */
function coverCrop(source, target) {
    const scale = Math.max(target.width / source.width, target.height / source.height);
    const w = Math.min(source.width, target.width / scale);
    const h = Math.min(source.height, target.height / scale);
    return { x: (source.width - w) / 2, y: (source.height - h) / 2, w, h };
}

/**
 * Decodes, resizes and encodes one image. `plan` maps the decoded size
 * to {size, crop?}; without one the image keeps its size.
 */
async function process(file, { format, quality, background, plan }) {
    const can = await browserSupport();
    const kind = await inspect(file);
    const inputFormat = INPUTS[kind.mime_type];
    if (!can.decode || !inputFormat || !file.size || (await isAnimated(file, kind.mime_type))) {
        return null;
    }
    const output = format === "auto" ? { JPEG: "jpg", PNG: "png", WEBP: "webp" }[inputFormat] : format;
    if (!MIME[output] || !can[output]) {
        return null;
    }

    const bitmap = await decode(file);
    try {
        const source = { width: bitmap.width, height: bitmap.height };
        if (source.width * source.height > MAX_PIXELS) {
            return null;
        }
        const planned = plan ? plan(source) : { size: source };
        if (!planned || planned.size.width * planned.size.height > MAX_PIXELS) {
            return null;
        }
        const { size } = planned;
        const crop = planned.crop || { x: 0, y: 0, w: source.width, h: source.height };
        let canvas = draw(bitmap, crop, size.width, size.height);

        const transparent = inputFormat !== "JPEG" && hasTransparency(canvas);
        const flattened = output === "jpg" && transparent;
        if (flattened) {
            const filled = newCanvas(size.width, size.height);
            const drawing = context(filled);
            drawing.fillStyle = background;
            drawing.fillRect(0, 0, size.width, size.height);
            drawing.drawImage(canvas, 0, 0);
            canvas = filled;
        }

        let blob;
        if (output === "png") {
            blob = await encodePng(context(canvas).getImageData(0, 0, size.width, size.height));
        } else {
            blob = await toBlob(canvas, MIME[output], (quality ?? DEFAULT_QUALITY[output]) / 100);
            if (blob.type !== MIME[output]) {
                return null;
            }
        }
        const stem = file.name.includes(".") ? file.name.slice(0, file.name.lastIndexOf(".")) : file.name;
        return {
            blob,
            filename: `${stem}.${output}`,
            format: output,
            inputFormat,
            source,
            size,
            flattened,
            hasAlpha: transparent && !flattened,
        };
    } finally {
        bitmap.close();
    }
}

function batchItem(file, done) {
    return {
        success: true,
        original_filename: file.name,
        output_filename: done.filename,
        input_format: done.inputFormat,
        output_format: done.format,
        original_width: done.source.width,
        original_height: done.source.height,
        width: done.size.width,
        height: done.size.height,
        original_size_bytes: file.size,
        size_bytes: done.blob.size,
        download_url: URL.createObjectURL(done.blob),
    };
}

function batch(files, items) {
    return {
        success: true,
        total_files: files.length,
        successful_files: items.length,
        failed_files: 0,
        results: items,
        failures: [],
    };
}

function single(file, done, details) {
    return {
        success: true,
        original_filename: file.name,
        width: done.size.width,
        height: done.size.height,
        format: done.format,
        filename: done.filename,
        size_bytes: done.blob.size,
        download_url: URL.createObjectURL(done.blob),
        details: {
            width: done.size.width,
            height: done.size.height,
            input_format: done.inputFormat,
            original_size: file.size,
            output_size: done.blob.size,
            ...details,
        },
    };
}

/** Runs every file through `one`; a single refusal sends the batch away. */
async function each(files, one) {
    const finished = [];
    for (const file of files) {
        const done = await one(file);
        if (!done) {
            finished.forEach((item) => URL.revokeObjectURL(item.download_url));
            return null;
        }
        finished.push(done);
    }
    return finished;
}

function encoding(fields, format) {
    const background = parseColor(fields.background_color);
    const quality = parseQuality(fields.quality);
    // Canvas output never carries metadata, so keeping it is the server's job.
    if (!background || quality === null || isFalse(fields.remove_metadata) || isTrue(fields.lossless)) {
        return null;
    }
    return { format, quality, background };
}

export async function convertTool(files, fields) {
    const format = String(fields.output_format || "png").toLowerCase();
    const options = encoding(fields, format);
    if (!options || !MIME[format]) {
        return null;
    }
    const items = await each(files, async (file) => {
        const done = await process(file, options);
        return (
            done && {
                ...batchItem(file, done),
                details: {
                    input_format: done.inputFormat,
                    original_width: done.source.width,
                    original_height: done.source.height,
                    original_size_bytes: file.size,
                    flattened: done.flattened,
                    has_alpha: done.hasAlpha,
                },
            }
        );
    });
    return items && batch(files, items);
}

export async function resizeTool(files, fields) {
    const requested = String(fields.output_format || "auto").toLowerCase();
    const format = requested === "jpeg" ? "jpg" : requested;
    const options = encoding(fields, format);
    const maxima = [optionalInt(fields.max_width), optionalInt(fields.max_height)].filter(
        (value) => value !== undefined
    );
    const sizing = {
        mode: fields.resize_mode || "aspect",
        width: optionalInt(fields.width),
        height: optionalInt(fields.height),
        percent: fields.percent === undefined || fields.percent === "" ? undefined : Number(fields.percent),
        maxDimension: maxima.length ? Math.max(...maxima) : undefined,
        upscale: isTrue(fields.allow_upscale),
    };
    if (!options || (format !== "auto" && !MIME[format])) {
        return null;
    }
    if (sizing.mode !== "max") {
        sizing.maxDimension = undefined;
    }
    const items = await each(files, async (file) => {
        const done = await process(file, {
            ...options,
            plan: (source) => {
                const size = newSize(source, sizing);
                return size && { size };
            },
        });
        return (
            done && {
                ...batchItem(file, done),
                details: {
                    input_format: done.inputFormat,
                    original_width: done.source.width,
                    original_height: done.source.height,
                    original_size_bytes: file.size,
                    output_format: done.format,
                    width: done.size.width,
                    height: done.size.height,
                    flattened: done.flattened,
                    has_alpha: done.hasAlpha,
                },
            }
        );
    });
    return items && batch(files, items);
}

/** The single-image resize behind the social media presets. */
export async function presetTool(files, fields) {
    const format = String(fields.output_format || "png").toLowerCase();
    const options = encoding(fields, format);
    const target = { width: optionalInt(fields.width), height: optionalInt(fields.height) };
    const fits = [target.width, target.height].every((side) => side > 0 && side <= MAX_SIDE);
    if (!options || !MIME[format] || files.length !== 1 || !fits || !isTrue(fields.cover)) {
        return null;
    }
    const [file] = files;
    const done = await process(file, {
        ...options,
        plan: (source) => ({ size: target, crop: coverCrop(source, target) }),
    });
    return (
        done &&
        single(file, done, {
            original_width: done.source.width,
            original_height: done.source.height,
            flattened: done.flattened,
            has_alpha: done.hasAlpha,
        })
    );
}

/**
 * Re-encodes an image without its metadata. The photo, and whatever
 * location it carries, never leaves the device.
 */
export async function metadataTool(files) {
    if (files.length !== 1) {
        return null;
    }
    const [file] = files;
    const kind = await inspect(file);
    const removed = await embeddedMetadata(file, kind.mime_type);
    if (!removed) {
        return null;
    }
    const done = await process(file, { format: "auto", quality: 95, background: "#ffffff" });
    return done && single(file, done, { removed_metadata: removed });
}

/**
 * A copy of the image no longer than `side` pixels on its longest side,
 * or the file itself when it is already small enough or cannot be read
 * here.
 */
export async function shrink(file, side) {
    try {
        const can = await browserSupport();
        const kind = await inspect(file);
        if (!can.decode || !INPUTS[kind.mime_type] || (await isAnimated(file, kind.mime_type))) {
            return file;
        }
        const bitmap = await decode(file);
        try {
            const { width, height } = bitmap;
            if (Math.max(width, height) <= side || width * height > MAX_PIXELS) {
                return file;
            }
            const ratio = side / Math.max(width, height);
            const canvas = draw(
                bitmap,
                { x: 0, y: 0, w: width, h: height },
                Math.max(1, Math.round(width * ratio)),
                Math.max(1, Math.round(height * ratio))
            );
            const lossless = !can.jpg || (INPUTS[kind.mime_type] !== "JPEG" && hasTransparency(canvas));
            if (lossless && !can.png) {
                return file;
            }
            const blob = lossless
                ? await encodePng(context(canvas).getImageData(0, 0, canvas.width, canvas.height))
                : await toBlob(canvas, MIME.jpg, 0.92);
            if (blob.size >= file.size) {
                return file;
            }
            const stem = file.name.includes(".") ? file.name.slice(0, file.name.lastIndexOf(".")) : file.name;
            return new File([blob], `${stem}.${lossless ? "png" : "jpg"}`, { type: blob.type });
        } finally {
            bitmap.close();
        }
    } catch {
        return file;
    }
}

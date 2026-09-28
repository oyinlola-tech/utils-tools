/**
 * PNG encoder.
 *
 * canvas.toBlob() writes PNGs for speed: always 32-bit, lightly
 * compressed, 70% to 290% larger than the server's on the images this
 * was measured with. This encoder picks the smallest pixel format the
 * image allows (palette, RGB, or RGBA), filters each row the way libpng
 * does, and deflates with the browser's CompressionStream.
 */
import { concat, crc32 } from "./bytes.js";

const SIGNATURE = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
const PALETTE = 3;
const RGB = 2;
const RGBA = 6;
const MAX_PALETTE = 256;
// Rows filtered between pauses that let the page stay responsive.
const ROWS_PER_SLICE = 256;

const pause = () => new Promise((resolve) => setTimeout(resolve, 0));

function chunk(type, data) {
    const bytes = new Uint8Array(12 + data.length);
    const view = new DataView(bytes.buffer);
    view.setUint32(0, data.length);
    for (let index = 0; index < 4; index += 1) {
        bytes[4 + index] = type.charCodeAt(index);
    }
    bytes.set(data, 8);
    view.setUint32(8 + data.length, crc32(bytes.subarray(4, 8 + data.length)));
    return bytes;
}

/** Colors in order of first use, or null once there are too many. */
function findPalette(pixels) {
    const colors = new Map();
    for (let index = 0; index < pixels.length; index += 1) {
        const color = pixels[index];
        if (!colors.has(color)) {
            if (colors.size === MAX_PALETTE) {
                return null;
            }
            colors.set(color, colors.size);
        }
    }
    return colors;
}

function isOpaque(rgba) {
    for (let index = 3; index < rgba.length; index += 4) {
        if (rgba[index] !== 255) {
            return false;
        }
    }
    return true;
}

function paletteScanlines(pixels, width, height, colors) {
    const lines = new Uint8Array((width + 1) * height);
    for (let row = 0; row < height; row += 1) {
        const out = row * (width + 1) + 1;
        const from = row * width;
        for (let column = 0; column < width; column += 1) {
            lines[out + column] = colors.get(pixels[from + column]);
        }
    }
    return lines;
}

function paletteChunks(colors) {
    const entries = new Uint8Array(colors.size * 3);
    const alphas = new Uint8Array(colors.size);
    let transparent = 0;
    // Pixels were read as little-endian words: red is the lowest byte.
    for (const [color, index] of colors) {
        entries[index * 3] = color & 0xff;
        entries[index * 3 + 1] = (color >>> 8) & 0xff;
        entries[index * 3 + 2] = (color >>> 16) & 0xff;
        alphas[index] = color >>> 24;
        if (alphas[index] !== 255) {
            transparent = index + 1;
        }
    }
    const chunks = [chunk("PLTE", entries)];
    if (transparent) {
        chunks.push(chunk("tRNS", alphas.subarray(0, transparent)));
    }
    return chunks;
}

function paeth(left, up, corner) {
    const estimate = left + up - corner;
    const toLeft = Math.abs(estimate - left);
    const toUp = Math.abs(estimate - up);
    const toCorner = Math.abs(estimate - corner);
    if (toLeft <= toUp && toLeft <= toCorner) {
        return left;
    }
    return toUp <= toCorner ? up : corner;
}

/**
 * Filters one row five ways and keeps the one with the smallest sum of
 * absolute values, the heuristic libpng uses to guess what deflates best.
 */
function filterRow(current, previous, stride, candidates, out, at) {
    const length = current.length;
    let best = 0;
    let bestCost = Infinity;
    for (let filter = 0; filter < 5; filter += 1) {
        const candidate = candidates[filter];
        let cost = 0;
        for (let index = 0; index < length; index += 1) {
            const left = index >= stride ? current[index - stride] : 0;
            const up = previous ? previous[index] : 0;
            let predicted = 0;
            if (filter === 1) {
                predicted = left;
            } else if (filter === 2) {
                predicted = up;
            } else if (filter === 3) {
                predicted = (left + up) >> 1;
            } else if (filter === 4) {
                const corner = previous && index >= stride ? previous[index - stride] : 0;
                predicted = paeth(left, up, corner);
            }
            const value = (current[index] - predicted) & 0xff;
            candidate[index] = value;
            cost += value < 128 ? value : 256 - value;
            if (cost >= bestCost) {
                break;
            }
        }
        if (cost < bestCost) {
            bestCost = cost;
            best = filter;
        }
    }
    out[at] = best;
    out.set(candidates[best], at + 1);
}

async function truecolorScanlines(rgba, width, height, stride) {
    const rowBytes = width * stride;
    const lines = new Uint8Array((rowBytes + 1) * height);
    const candidates = Array.from({ length: 5 }, () => new Uint8Array(rowBytes));
    let current = new Uint8Array(rowBytes);
    let previous = null;
    let spare = new Uint8Array(rowBytes);
    for (let row = 0; row < height; row += 1) {
        const from = row * width * 4;
        if (stride === 4) {
            current.set(rgba.subarray(from, from + rowBytes));
        } else {
            for (let column = 0; column < width; column += 1) {
                current[column * 3] = rgba[from + column * 4];
                current[column * 3 + 1] = rgba[from + column * 4 + 1];
                current[column * 3 + 2] = rgba[from + column * 4 + 2];
            }
        }
        filterRow(current, previous, stride, candidates, lines, row * (rowBytes + 1));
        const finished = current;
        current = previous || spare;
        previous = finished;
        if (row % ROWS_PER_SLICE === ROWS_PER_SLICE - 1) {
            await pause();
        }
    }
    return lines;
}

async function deflate(bytes) {
    const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream("deflate"));
    return new Uint8Array(await new Response(stream).arrayBuffer());
}

export function canEncodePng() {
    return typeof CompressionStream === "function";
}

/** Encodes canvas pixels ({data, width, height}) as a PNG Blob. */
export async function encodePng({ data, width, height }) {
    const pixels = new Uint32Array(data.buffer, data.byteOffset, data.byteLength / 4);
    const colors = findPalette(pixels);
    const header = new Uint8Array(13);
    const view = new DataView(header.buffer);
    view.setUint32(0, width);
    view.setUint32(4, height);
    header[8] = 8;

    let scanlines;
    const extra = [];
    if (colors) {
        header[9] = PALETTE;
        scanlines = paletteScanlines(pixels, width, height, colors);
        extra.push(...paletteChunks(colors));
    } else if (isOpaque(data)) {
        header[9] = RGB;
        scanlines = await truecolorScanlines(data, width, height, 3);
    } else {
        header[9] = RGBA;
        scanlines = await truecolorScanlines(data, width, height, 4);
    }

    return new Blob(
        [
            concat([
                Uint8Array.from(SIGNATURE),
                chunk("IHDR", header),
                ...extra,
                chunk("IDAT", await deflate(scanlines)),
                chunk("IEND", new Uint8Array(0)),
            ]),
        ],
        { type: "image/png" }
    );
}

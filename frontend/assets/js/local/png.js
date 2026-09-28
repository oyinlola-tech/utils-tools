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

function paletteIndexes(pixels, colors) {
    const indexes = new Uint8Array(pixels.length);
    for (let index = 0; index < pixels.length; index += 1) {
        indexes[index] = colors.get(pixels[index]);
    }
    return indexes;
}

function unfilteredScanlines(bytes, rowBytes, height) {
    const lines = new Uint8Array((rowBytes + 1) * height);
    for (let row = 0; row < height; row += 1) {
        lines.set(bytes.subarray(row * rowBytes, (row + 1) * rowBytes), row * (rowBytes + 1) + 1);
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

const cost = (value) => (value < 128 ? value : 256 - value);

/**
 * Filters one row five ways and keeps the one with the smallest sum of
 * absolute values, the heuristic libpng uses to guess what deflates
 * best. One pass computes all five: this loop runs once for every byte
 * of the image, and is most of the time the encoder takes.
 */
function filterRow(current, previous, stride, candidates, out, at) {
    const [none, sub, up, average, paeth] = candidates;
    const costs = [0, 0, 0, 0, 0];
    const length = current.length;
    for (let index = 0; index < length; index += 1) {
        const value = current[index];
        const above = previous[index];
        let left = 0;
        let corner = 0;
        if (index >= stride) {
            left = current[index - stride];
            corner = previous[index - stride];
        }
        const estimate = left + above - corner;
        const toLeft = estimate > left ? estimate - left : left - estimate;
        const toAbove = estimate > above ? estimate - above : above - estimate;
        const toCorner = estimate > corner ? estimate - corner : corner - estimate;
        let nearest = corner;
        if (toLeft <= toAbove && toLeft <= toCorner) {
            nearest = left;
        } else if (toAbove <= toCorner) {
            nearest = above;
        }

        costs[0] += cost((none[index] = value));
        costs[1] += cost((sub[index] = (value - left) & 0xff));
        costs[2] += cost((up[index] = (value - above) & 0xff));
        costs[3] += cost((average[index] = (value - ((left + above) >> 1)) & 0xff));
        costs[4] += cost((paeth[index] = (value - nearest) & 0xff));
    }
    const best = costs.indexOf(Math.min(...costs));
    out[at] = best;
    out.set(candidates[best], at + 1);
}

/**
 * Scanlines with the best filter chosen for each row. `source` holds
 * `sourceStride` bytes a pixel, of which the first `stride` are kept:
 * RGBA pixels written as RGB drop their alpha here.
 */
async function filteredScanlines(source, width, height, sourceStride, stride) {
    const rowBytes = width * stride;
    const lines = new Uint8Array((rowBytes + 1) * height);
    const candidates = Array.from({ length: 5 }, () => new Uint8Array(rowBytes));
    const rows = [new Uint8Array(rowBytes), new Uint8Array(rowBytes)];
    // The row above the first one counts as zeros.
    let previous = new Uint8Array(rowBytes);
    for (let row = 0; row < height; row += 1) {
        const current = rows[row % 2];
        const from = row * width * sourceStride;
        if (stride === sourceStride) {
            current.set(source.subarray(from, from + rowBytes));
        } else {
            for (let column = 0; column < width; column += 1) {
                for (let channel = 0; channel < stride; channel += 1) {
                    current[column * stride + channel] = source[from + column * sourceStride + channel];
                }
            }
        }
        filterRow(current, previous, stride, candidates, lines, row * (rowBytes + 1));
        previous = current;
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

    let compressed;
    const extra = [];
    if (colors) {
        header[9] = PALETTE;
        extra.push(...paletteChunks(colors));
        // Filtering usually hurts indexed pixels, but not when rows
        // repeat, as they do in screenshots. These images are small
        // enough to try both.
        const indexes = paletteIndexes(pixels, colors);
        const [plain, filtered] = await Promise.all([
            deflate(unfilteredScanlines(indexes, width, height)),
            deflate(await filteredScanlines(indexes, width, height, 1, 1)),
        ]);
        compressed = filtered.length < plain.length ? filtered : plain;
    } else if (isOpaque(data)) {
        header[9] = RGB;
        compressed = await deflate(await filteredScanlines(data, width, height, 4, 3));
    } else {
        header[9] = RGBA;
        compressed = await deflate(await filteredScanlines(data, width, height, 4, 4));
    }

    return new Blob(
        [
            concat([
                Uint8Array.from(SIGNATURE),
                chunk("IHDR", header),
                ...extra,
                chunk("IDAT", compressed),
                chunk("IEND", new Uint8Array(0)),
            ]),
        ],
        { type: "image/png" }
    );
}

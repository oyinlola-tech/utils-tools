export const ALGORITHMS = ["MD5", "SHA-1", "SHA-256", "SHA-384", "SHA-512"];

const SHIFTS = [
    7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
    5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
    4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
    6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21,
];

const K = new Uint32Array(64);
for (let i = 0; i < 64; i += 1) {
    K[i] = Math.floor(Math.abs(Math.sin(i + 1)) * 2 ** 32);
}

/** Streaming MD5 (RFC 1321). crypto.subtle deliberately omits MD5. */
export class Md5 {
    constructor() {
        this.state = new Uint32Array([0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476]);
        this.buffer = new Uint8Array(64);
        this.bufferLength = 0;
        this.totalLength = 0;
        this.words = new Uint32Array(16);
    }

    block(bytes, offset) {
        const m = this.words;
        for (let i = 0; i < 16; i += 1) {
            const j = offset + i * 4;
            m[i] = bytes[j] | (bytes[j + 1] << 8) | (bytes[j + 2] << 16) | (bytes[j + 3] << 24);
        }
        let [a, b, c, d] = this.state;
        for (let i = 0; i < 64; i += 1) {
            let f;
            let g;
            if (i < 16) {
                f = (b & c) | (~b & d);
                g = i;
            } else if (i < 32) {
                f = (d & b) | (~d & c);
                g = (5 * i + 1) % 16;
            } else if (i < 48) {
                f = b ^ c ^ d;
                g = (3 * i + 5) % 16;
            } else {
                f = c ^ (b | ~d);
                g = (7 * i) % 16;
            }
            const sum = (a + f + K[i] + m[g]) | 0;
            a = d;
            d = c;
            c = b;
            b = (b + ((sum << SHIFTS[i]) | (sum >>> (32 - SHIFTS[i])))) | 0;
        }
        this.state[0] += a;
        this.state[1] += b;
        this.state[2] += c;
        this.state[3] += d;
    }

    update(input) {
        const bytes = input instanceof Uint8Array ? input : new Uint8Array(input);
        this.totalLength += bytes.length;
        let offset = 0;
        if (this.bufferLength > 0) {
            const take = Math.min(64 - this.bufferLength, bytes.length);
            this.buffer.set(bytes.subarray(0, take), this.bufferLength);
            this.bufferLength += take;
            offset = take;
            if (this.bufferLength === 64) {
                this.block(this.buffer, 0);
                this.bufferLength = 0;
            }
        }
        while (offset + 64 <= bytes.length) {
            this.block(bytes, offset);
            offset += 64;
        }
        if (offset < bytes.length) {
            this.buffer.set(bytes.subarray(offset), 0);
            this.bufferLength = bytes.length - offset;
        }
        return this;
    }

    digest() {
        const bitLength = this.totalLength * 8;
        const padLength = this.bufferLength < 56 ? 56 - this.bufferLength : 120 - this.bufferLength;
        const padding = new Uint8Array(padLength + 8);
        padding[0] = 0x80;
        const view = new DataView(padding.buffer);
        view.setUint32(padLength, bitLength >>> 0, true);
        view.setUint32(padLength + 4, Math.floor(bitLength / 2 ** 32), true);
        const total = this.totalLength;
        this.update(padding);
        this.totalLength = total;
        const out = new Uint8Array(16);
        const outView = new DataView(out.buffer);
        for (let i = 0; i < 4; i += 1) {
            outView.setUint32(i * 4, this.state[i], true);
        }
        return out;
    }
}

export function md5(bytes) {
    return new Md5().update(bytes).digest();
}

function concat(a, b) {
    const out = new Uint8Array(a.length + b.length);
    out.set(a, 0);
    out.set(b, a.length);
    return out;
}

export function hmacMd5(key, message) {
    let keyBytes = key.length > 64 ? md5(key) : key;
    const padded = new Uint8Array(64);
    padded.set(keyBytes);
    keyBytes = padded;
    const inner = keyBytes.map((byte) => byte ^ 0x36);
    const outer = keyBytes.map((byte) => byte ^ 0x5c);
    return md5(concat(outer, md5(concat(inner, message))));
}

export async function digest(algorithm, bytes) {
    if (algorithm === "MD5") {
        return md5(bytes);
    }
    const result = await globalThis.crypto.subtle.digest(algorithm, bytes);
    return new Uint8Array(result);
}

export async function hmac(algorithm, key, bytes) {
    if (algorithm === "MD5") {
        return hmacMd5(key, bytes);
    }
    const cryptoKey = await globalThis.crypto.subtle.importKey(
        "raw",
        // Web Crypto rejects empty HMAC keys; one zero byte pads to the same block.
        key.length ? key : new Uint8Array(1),
        { name: "HMAC", hash: algorithm },
        false,
        ["sign"]
    );
    const signature = await globalThis.crypto.subtle.sign("HMAC", cryptoKey, bytes);
    return new Uint8Array(signature);
}

export function toHex(bytes) {
    let out = "";
    for (const byte of bytes) {
        out += byte.toString(16).padStart(2, "0");
    }
    return out;
}

export function toBase64(bytes) {
    let binary = "";
    for (let i = 0; i < bytes.length; i += 0x8000) {
        binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    }
    return btoa(binary);
}

export function encodeDigest(bytes, format = "hex") {
    if (format === "base64") {
        return toBase64(bytes);
    }
    const hex = toHex(bytes);
    return format === "HEX" ? hex.toUpperCase() : hex;
}

export async function hashAll(bytes, { key = null, algorithms = ALGORITHMS } = {}) {
    const results = {};
    for (const algorithm of algorithms) {
        results[algorithm] = key ? await hmac(algorithm, key, bytes) : await digest(algorithm, bytes);
    }
    return results;
}

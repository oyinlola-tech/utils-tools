const CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

export function randomBytes(length) {
    const bytes = new Uint8Array(length);
    globalThis.crypto.getRandomValues(bytes);
    return bytes;
}

function toHex(bytes) {
    let out = "";
    for (const byte of bytes) {
        out += byte.toString(16).padStart(2, "0");
    }
    return out;
}

function formatUuid(bytes) {
    const hex = toHex(bytes);
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function uuidv4(rng = randomBytes) {
    const bytes = rng(16);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    return formatUuid(bytes);
}

function writeTimestamp48(bytes, ms) {
    let value = BigInt(ms);
    for (let i = 5; i >= 0; i -= 1) {
        bytes[i] = Number(value & 0xffn);
        value >>= 8n;
    }
}

/**
 * UUIDv7 generator (RFC 9562). Within one millisecond the 12-bit rand_a
 * field is used as a counter (RFC 9562 section 6.2, method 1) so that a
 * bulk batch sorts in generation order.
 */
export function createUuidV7Generator({ rng = randomBytes, now = () => Date.now() } = {}) {
    let lastMs = -1;
    let counter = 0;
    return function uuidv7() {
        let ms = now();
        if (ms <= lastMs) {
            counter += 1;
            if (counter > 0xfff) {
                lastMs += 1;
                counter = rng(1)[0] & 0x7f;
            }
            ms = lastMs;
        } else {
            lastMs = ms;
            // Seed below 0x800 to leave headroom for increments.
            const seed = rng(2);
            counter = ((seed[0] << 8) | seed[1]) & 0x7ff;
        }
        const bytes = rng(16);
        writeTimestamp48(bytes, ms);
        bytes[6] = 0x70 | ((counter >> 8) & 0x0f);
        bytes[7] = counter & 0xff;
        bytes[8] = (bytes[8] & 0x3f) | 0x80;
        return formatUuid(bytes);
    };
}

function encodeTime(ms) {
    let out = "";
    let value = ms;
    for (let i = 0; i < 10; i += 1) {
        out = CROCKFORD[value % 32] + out;
        value = Math.floor(value / 32);
    }
    return out;
}

function encodeRandom(bytes) {
    let value = 0n;
    for (const byte of bytes) {
        value = (value << 8n) | BigInt(byte);
    }
    let out = "";
    for (let i = 0; i < 16; i += 1) {
        out = CROCKFORD[Number(value & 31n)] + out;
        value >>= 5n;
    }
    return out;
}

/** Monotonic ULID generator: same-millisecond IDs increment the random part. */
export function createUlidGenerator({ rng = randomBytes, now = () => Date.now() } = {}) {
    let lastMs = -1;
    let lastRandom = null;
    return function ulid() {
        let ms = now();
        if (ms <= lastMs && lastRandom) {
            ms = lastMs;
            const next = Uint8Array.from(lastRandom);
            for (let i = next.length - 1; i >= 0; i -= 1) {
                if (next[i] === 0xff) {
                    next[i] = 0;
                    continue;
                }
                next[i] += 1;
                break;
            }
            lastRandom = next;
        } else {
            lastMs = ms;
            lastRandom = rng(10);
        }
        return encodeTime(ms) + encodeRandom(lastRandom);
    };
}

export function formatId(id, { uppercase = false, hyphens = true, braces = false } = {}) {
    let out = id;
    if (!hyphens) {
        out = out.replace(/-/g, "");
    }
    out = uppercase ? out.toUpperCase() : out.toLowerCase();
    if (braces) {
        out = `{${out}}`;
    }
    return out;
}

export function uuidTimestamp(uuid) {
    const hex = uuid.replace(/[{}-]/g, "").toLowerCase();
    if (!/^[0-9a-f]{32}$/.test(hex) || hex[12] !== "7") {
        return null;
    }
    return parseInt(hex.slice(0, 12), 16);
}

export function ulidTimestamp(ulid) {
    const text = ulid.toUpperCase();
    if (!/^[0-9A-HJKMNP-TV-Z]{26}$/.test(text)) {
        return null;
    }
    let ms = 0;
    for (const char of text.slice(0, 10)) {
        ms = ms * 32 + CROCKFORD.indexOf(char);
    }
    return ms;
}

export function generateIds({ kind = "v4", count = 1, rng = randomBytes, now = () => Date.now() } = {}) {
    const total = Math.max(1, Math.min(1000, Math.floor(count) || 1));
    let make;
    if (kind === "v7") {
        make = createUuidV7Generator({ rng, now });
    } else if (kind === "ulid") {
        make = createUlidGenerator({ rng, now });
    } else if (kind === "nil") {
        make = () => "00000000-0000-0000-0000-000000000000";
    } else {
        make = () => uuidv4(rng);
    }
    const ids = [];
    for (let i = 0; i < total; i += 1) {
        ids.push(make());
    }
    return ids;
}

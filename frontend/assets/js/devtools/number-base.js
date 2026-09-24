const DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz";
const PREFIXES = { 2: /^0b/i, 8: /^0o/i, 16: /^0x/i };

export function parseInBase(input, base) {
    if (!Number.isInteger(base) || base < 2 || base > 36) {
        throw new Error("Base must be between 2 and 36.");
    }
    let text = String(input).trim().replace(/[\s_',]/g, "").toLowerCase();
    if (!text) {
        return null;
    }
    let negative = false;
    if (text[0] === "-" || text[0] === "+") {
        negative = text[0] === "-";
        text = text.slice(1);
    }
    if (PREFIXES[base]) {
        text = text.replace(PREFIXES[base], "");
    }
    if (!text) {
        throw new Error(`Enter at least one base-${base} digit.`);
    }
    const bigBase = BigInt(base);
    let value = 0n;
    for (const char of text) {
        const digit = DIGITS.indexOf(char);
        if (digit < 0 || digit >= base) {
            throw new Error(`"${char}" is not a valid base-${base} digit.`);
        }
        value = value * bigBase + BigInt(digit);
    }
    return negative ? -value : value;
}

export function formatInBase(value, base, { uppercase = false, group = 0 } = {}) {
    if (value === null || value === undefined) {
        return "";
    }
    const negative = value < 0n;
    let text = (negative ? -value : value).toString(base);
    if (uppercase) {
        text = text.toUpperCase();
    }
    if (group > 0 && text.length > group) {
        const head = text.length % group;
        const parts = head ? [text.slice(0, head)] : [];
        for (let i = head; i < text.length; i += group) {
            parts.push(text.slice(i, i + group));
        }
        text = parts.join(" ");
    }
    return negative ? `-${text}` : text;
}

export function bitLength(value) {
    if (value === null || value === undefined) {
        return 0;
    }
    const abs = value < 0n ? -value : value;
    return abs === 0n ? 1 : abs.toString(2).length;
}

export function twosComplement(value, bits) {
    if (value === null || value === undefined || value >= 0n) {
        return null;
    }
    const width = BigInt(bits);
    if (-value > 1n << (width - 1n)) {
        return null;
    }
    return ((1n << width) + value).toString(2).padStart(bits, "1");
}

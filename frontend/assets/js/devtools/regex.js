export const FLAG_ORDER = "dgimsuvy";

export function normalizeFlags(flags) {
    const set = new Set(String(flags).split(""));
    return FLAG_ORDER.split("").filter((flag) => set.has(flag)).join("");
}

export function buildRegex(pattern, flags) {
    try {
        return { regex: new RegExp(pattern, normalizeFlags(flags)), error: null };
    } catch (error) {
        return { regex: null, error: error.message.replace(/^Invalid regular expression: /, "") };
    }
}

export function findMatches(pattern, flags, text, { limit = 1000 } = {}) {
    const { regex, error } = buildRegex(pattern, flags);
    if (error) {
        return { error, matches: [], truncated: false };
    }
    const matches = [];
    const toMatch = (m) => ({
        index: m.index,
        end: m.index + m[0].length,
        text: m[0],
        groups: m.slice(1),
        named: m.groups ? { ...m.groups } : null,
    });
    if (!regex.global) {
        const m = regex.exec(text);
        if (m) {
            matches.push(toMatch(m));
        }
        return { error: null, matches, truncated: false };
    }
    let truncated = false;
    for (const m of text.matchAll(regex)) {
        if (matches.length >= limit) {
            truncated = true;
            break;
        }
        matches.push(toMatch(m));
    }
    return { error: null, matches, truncated };
}

/** Split text into alternating plain/match segments for highlighting. */
export function segments(text, matches) {
    const out = [];
    let cursor = 0;
    matches.forEach((match, i) => {
        if (match.index > cursor) {
            out.push({ text: text.slice(cursor, match.index), match: -1 });
        }
        if (match.end > match.index) {
            out.push({ text: text.slice(match.index, match.end), match: i });
        }
        cursor = Math.max(cursor, match.end);
    });
    if (cursor < text.length) {
        out.push({ text: text.slice(cursor), match: -1 });
    }
    return out;
}

export function replaceAll(pattern, flags, text, replacement) {
    const { regex, error } = buildRegex(pattern, flags);
    if (error) {
        return { error, result: "" };
    }
    return { error: null, result: text.replace(regex, replacement) };
}

export function runRegex({ pattern, flags, text, replacement = null, limit = 1000 }) {
    const found = findMatches(pattern, flags, text, { limit });
    let replaced = null;
    if (!found.error && replacement !== null) {
        replaced = replaceAll(pattern, flags, text, replacement).result;
    }
    return { ...found, replaced };
}

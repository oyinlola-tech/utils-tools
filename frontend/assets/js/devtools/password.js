export const SETS = {
    lower: "abcdefghijklmnopqrstuvwxyz",
    upper: "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    digits: "0123456789",
    symbols: "!@#$%^&*()-_=+[]{};:,.?/~",
};

const AMBIGUOUS = /[Il1O0o|`'"]/g;

export function defaultRandomUint32() {
    const buffer = new Uint32Array(1);
    globalThis.crypto.getRandomValues(buffer);
    return buffer[0];
}

/** Uniform integer in [0, max) via rejection sampling, so there is no modulo bias. */
export function randomInt(max, rand32 = defaultRandomUint32) {
    if (max <= 0 || max > 2 ** 32) {
        throw new Error("randomInt range out of bounds.");
    }
    const limit = 2 ** 32 - (2 ** 32 % max);
    let value = rand32();
    while (value >= limit) {
        value = rand32();
    }
    return value % max;
}

function shuffle(chars, rand32) {
    for (let i = chars.length - 1; i > 0; i -= 1) {
        const j = randomInt(i + 1, rand32);
        [chars[i], chars[j]] = [chars[j], chars[i]];
    }
    return chars;
}

export function activeSets({ lower = true, upper = true, digits = true, symbols = true, excludeAmbiguous = false } = {}) {
    const chosen = { lower, upper, digits, symbols };
    return Object.keys(SETS)
        .filter((name) => chosen[name])
        .map((name) => (excludeAmbiguous ? SETS[name].replace(AMBIGUOUS, "") : SETS[name]))
        .filter(Boolean);
}

export function generatePassword(options = {}, rand32 = defaultRandomUint32) {
    const length = Math.max(4, Math.min(256, Math.floor(options.length) || 20));
    const sets = activeSets(options);
    if (!sets.length) {
        throw new Error("Select at least one character set.");
    }
    const pool = sets.join("");
    // One character from every selected set, then fill from the whole pool.
    const chars = sets.map((set) => set[randomInt(set.length, rand32)]);
    while (chars.length < length) {
        chars.push(pool[randomInt(pool.length, rand32)]);
    }
    return shuffle(chars, rand32).slice(0, length).join("");
}

export function passwordEntropy(options = {}) {
    const pool = activeSets(options).join("").length;
    const length = Math.max(4, Math.min(256, Math.floor(options.length) || 20));
    return pool ? length * Math.log2(pool) : 0;
}

export function generatePassphrase(
    { words = 5, separator = "-", capitalize = false, includeNumber = false } = {},
    wordlist,
    rand32 = defaultRandomUint32
) {
    const count = Math.max(3, Math.min(20, Math.floor(words) || 5));
    const picked = [];
    for (let i = 0; i < count; i += 1) {
        let word = wordlist[randomInt(wordlist.length, rand32)];
        if (capitalize) {
            word = word[0].toUpperCase() + word.slice(1);
        }
        picked.push(word);
    }
    if (includeNumber) {
        const index = randomInt(picked.length, rand32);
        picked[index] += String(randomInt(10, rand32));
    }
    return picked.join(separator);
}

export function passphraseEntropy({ words = 5, includeNumber = false } = {}, listSize) {
    const count = Math.max(3, Math.min(20, Math.floor(words) || 5));
    let bits = count * Math.log2(listSize);
    if (includeNumber) {
        bits += Math.log2(10) + Math.log2(count);
    }
    return bits;
}

export function strength(bits) {
    if (bits < 36) return { label: "Weak", score: 1 };
    if (bits < 60) return { label: "Fair", score: 2 };
    if (bits < 80) return { label: "Strong", score: 3 };
    return { label: "Very strong", score: 4 };
}

const SECONDS = [
    ["centuries", 3.15e9],
    ["years", 3.15e7],
    ["days", 86400],
    ["hours", 3600],
    ["minutes", 60],
];

/** Average time to brute force at 1e10 guesses per second (offline, fast hash). */
export function crackTime(bits, guessesPerSecond = 1e10) {
    const seconds = 2 ** (bits - 1) / guessesPerSecond;
    if (seconds < 1) return "less than a second";
    if (seconds > 3.15e9 * 1e6) return "longer than the age of the universe";
    for (const [unit, size] of SECONDS) {
        if (seconds >= size) {
            const value = seconds / size;
            return `about ${value >= 1000 ? value.toExponential(1) : Math.round(value)} ${unit}`;
        }
    }
    return `about ${Math.round(seconds)} seconds`;
}

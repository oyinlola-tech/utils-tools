const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

function trimNumber(value, digits) {
    return String(Number(value.toFixed(digits)));
}

function parseAlpha(token) {
    if (token === undefined) {
        return 1;
    }
    const value = token.endsWith("%") ? parseFloat(token) / 100 : parseFloat(token);
    if (Number.isNaN(value)) {
        throw new Error("Invalid alpha value.");
    }
    return clamp(value, 0, 1);
}

function parseHue(token) {
    if (token === "none") {
        return 0;
    }
    const value = parseFloat(token);
    if (Number.isNaN(value)) {
        throw new Error("Invalid hue.");
    }
    if (token.endsWith("turn")) return value * 360;
    if (token.endsWith("grad")) return value * 0.9;
    if (token.endsWith("rad")) return (value * 180) / Math.PI;
    return value;
}

function parsePercent(token, scale = 1) {
    if (token === "none") {
        return 0;
    }
    const value = parseFloat(token);
    if (Number.isNaN(value)) {
        throw new Error("Invalid number in color.");
    }
    return token.endsWith("%") ? (value / 100) * scale : value;
}

function splitArgs(body) {
    const [main, slashAlpha] = body.split("/");
    const parts = main.trim().split(/[\s,]+/).filter(Boolean);
    if (slashAlpha !== undefined) {
        parts.push(slashAlpha.trim());
    }
    return { parts, hasSlash: slashAlpha !== undefined };
}

function hslToRgb(h, s, l) {
    const hue = ((h % 360) + 360) % 360;
    const k = (n) => (n + hue / 30) % 12;
    const a = s * Math.min(l, 1 - l);
    const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
    return [f(0) * 255, f(8) * 255, f(4) * 255];
}

function hwbToRgb(h, w, b) {
    if (w + b >= 1) {
        const gray = (w / (w + b)) * 255;
        return [gray, gray, gray];
    }
    return hslToRgb(h, 1, 0.5).map((c) => (c / 255) * (1 - w - b) * 255 + w * 255);
}

const toLinear = (c) => {
    const v = c / 255;
    return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
};
const fromLinear = (v) => (v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055) * 255;

export function rgbToOklab({ r, g, b }) {
    const lr = toLinear(r);
    const lg = toLinear(g);
    const lb = toLinear(b);
    const l = Math.cbrt(0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb);
    const m = Math.cbrt(0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb);
    const s = Math.cbrt(0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb);
    return {
        L: 0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
        a: 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
        b: 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
    };
}

export function oklabToRgb(L, a, b) {
    const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3;
    const m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3;
    const s = (L - 0.0894841775 * a - 1.291485548 * b) ** 3;
    return [
        fromLinear(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s),
        fromLinear(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s),
        fromLinear(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s),
    ];
}

function finish([r, g, b], a) {
    const inGamut = [r, g, b].every((c) => c >= -0.5 && c <= 255.5);
    return { r: clamp(r, 0, 255), g: clamp(g, 0, 255), b: clamp(b, 0, 255), a, inGamut };
}

/**
 * Parse HEX, rgb(), hsl(), hwb(), oklab() and oklch(). Anything else
 * (named colors, lab(), color()) is delegated to the optional resolver,
 * which the browser page backs with the canvas color parser.
 */
export function parseColor(input, resolve = null) {
    const text = String(input).trim().toLowerCase();
    if (!text) {
        throw new Error("Enter a color.");
    }
    const hex = text.match(/^#?([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/);
    if (hex) {
        let digits = hex[1];
        if (digits.length <= 4) {
            digits = digits.split("").map((d) => d + d).join("");
        }
        const n = (i) => parseInt(digits.slice(i, i + 2), 16);
        return finish([n(0), n(2), n(4)], digits.length === 8 ? n(6) / 255 : 1);
    }
    const fn = text.match(/^(rgba?|hsla?|hwb|oklab|oklch)\((.*)\)$/);
    if (fn) {
        const { parts } = splitArgs(fn[2]);
        if (parts.length < 3 || parts.length > 4) {
            throw new Error(`${fn[1]}() needs three values plus an optional alpha.`);
        }
        const alpha = parseAlpha(parts[3]);
        switch (fn[1]) {
            case "rgb":
            case "rgba":
                return finish(parts.slice(0, 3).map((p) => parsePercent(p, 255)), alpha);
            case "hsl":
            case "hsla":
                return finish(hslToRgb(parseHue(parts[0]), parsePercent(parts[1], 100) / 100, parsePercent(parts[2], 100) / 100), alpha);
            case "hwb":
                return finish(hwbToRgb(parseHue(parts[0]), parsePercent(parts[1], 100) / 100, parsePercent(parts[2], 100) / 100), alpha);
            case "oklab":
                return finish(oklabToRgb(parsePercent(parts[0]), parsePercent(parts[1], 0.4), parsePercent(parts[2], 0.4)), alpha);
            case "oklch": {
                const L = parsePercent(parts[0]);
                const C = parsePercent(parts[1], 0.4);
                const H = (parseHue(parts[2]) * Math.PI) / 180;
                return finish(oklabToRgb(L, C * Math.cos(H), C * Math.sin(H)), alpha);
            }
            default:
                break;
        }
    }
    if (resolve) {
        const resolved = resolve(text);
        if (resolved && resolved !== text) {
            return parseColor(resolved);
        }
    }
    throw new Error("Unrecognized color. Try #1e90ff, rgb(30 144 255), hsl(210 100% 56%) or oklch(65% 0.18 250).");
}

export function rgbToHsl({ r, g, b }) {
    const rn = r / 255;
    const gn = g / 255;
    const bn = b / 255;
    const max = Math.max(rn, gn, bn);
    const min = Math.min(rn, gn, bn);
    const l = (max + min) / 2;
    const d = max - min;
    let h = 0;
    let s = 0;
    if (d !== 0) {
        s = d / (1 - Math.abs(2 * l - 1));
        if (max === rn) h = ((gn - bn) / d) % 6;
        else if (max === gn) h = (bn - rn) / d + 2;
        else h = (rn - gn) / d + 4;
        h *= 60;
        if (h < 0) h += 360;
    }
    return { h, s: s * 100, l: l * 100 };
}

const hex2 = (value) => Math.round(clamp(value, 0, 255)).toString(16).padStart(2, "0");

export function formatColor(color) {
    const { r, g, b, a } = color;
    const R = Math.round(r);
    const G = Math.round(g);
    const B = Math.round(b);
    const hasAlpha = a < 1;
    const alphaText = trimNumber(a, 3);
    const hsl = rgbToHsl(color);
    const max = Math.max(r, g, b) / 255;
    const min = Math.min(r, g, b) / 255;
    const lab = rgbToOklab(color);
    const chroma = Math.hypot(lab.a, lab.b);
    let hue = (Math.atan2(lab.b, lab.a) * 180) / Math.PI;
    if (hue < 0) hue += 360;
    const achromatic = chroma < 0.0002;
    const slash = hasAlpha ? ` / ${alphaText}` : "";
    return {
        hex: `#${hex2(r)}${hex2(g)}${hex2(b)}${hasAlpha ? hex2(a * 255) : ""}`,
        rgb: hasAlpha ? `rgba(${R}, ${G}, ${B}, ${alphaText})` : `rgb(${R}, ${G}, ${B})`,
        hsl: hasAlpha
            ? `hsla(${trimNumber(hsl.h, 1)}, ${trimNumber(hsl.s, 1)}%, ${trimNumber(hsl.l, 1)}%, ${alphaText})`
            : `hsl(${trimNumber(hsl.h, 1)}, ${trimNumber(hsl.s, 1)}%, ${trimNumber(hsl.l, 1)}%)`,
        hwb: `hwb(${trimNumber(hsl.h, 1)} ${trimNumber(min * 100, 1)}% ${trimNumber((1 - max) * 100, 1)}%${slash})`,
        oklab: `oklab(${trimNumber(lab.L * 100, 2)}% ${trimNumber(lab.a, 4)} ${trimNumber(lab.b, 4)}${slash})`,
        oklch: `oklch(${trimNumber(lab.L * 100, 2)}% ${trimNumber(achromatic ? 0 : chroma, 4)} ${achromatic ? "none" : trimNumber(hue, 2)}${slash})`,
    };
}

export function relativeLuminance({ r, g, b }) {
    return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
}

export function composite(top, bottom) {
    const a = top.a;
    return {
        r: top.r * a + bottom.r * (1 - a),
        g: top.g * a + bottom.g * (1 - a),
        b: top.b * a + bottom.b * (1 - a),
        a: 1,
    };
}

const WHITE = { r: 255, g: 255, b: 255, a: 1 };

export function contrastRatio(foreground, background) {
    const bg = background.a < 1 ? composite(background, WHITE) : background;
    const fg = foreground.a < 1 ? composite(foreground, bg) : foreground;
    const l1 = relativeLuminance(fg);
    const l2 = relativeLuminance(bg);
    const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
    return (hi + 0.05) / (lo + 0.05);
}

export function wcagResults(ratio) {
    return [
        { label: "AA · normal text", threshold: 4.5 },
        { label: "AA · large text (24px, or 18.66px bold)", threshold: 3 },
        { label: "AAA · normal text", threshold: 7 },
        { label: "AAA · large text", threshold: 4.5 },
        { label: "AA · UI components and graphics", threshold: 3 },
    ].map((item) => ({ ...item, pass: ratio >= item.threshold }));
}

export function toPickerHex(color) {
    return `#${hex2(color.r)}${hex2(color.g)}${hex2(color.b)}`;
}

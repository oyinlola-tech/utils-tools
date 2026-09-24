const LATIN1 =
    "nbsp iexcl cent pound curren yen brvbar sect uml copy ordf laquo not shy reg macr " +
    "deg plusmn sup2 sup3 acute micro para middot cedil sup1 ordm raquo frac14 frac12 frac34 iquest " +
    "Agrave Aacute Acirc Atilde Auml Aring AElig Ccedil Egrave Eacute Ecirc Euml Igrave Iacute Icirc Iuml " +
    "ETH Ntilde Ograve Oacute Ocirc Otilde Ouml times Oslash Ugrave Uacute Ucirc Uuml Yacute THORN szlig " +
    "agrave aacute acirc atilde auml aring aelig ccedil egrave eacute ecirc euml igrave iacute icirc iuml " +
    "eth ntilde ograve oacute ocirc otilde ouml divide oslash ugrave uacute ucirc uuml yacute thorn yuml";

const GREEK_UPPER =
    "Alpha Beta Gamma Delta Epsilon Zeta Eta Theta Iota Kappa Lambda Mu Nu Xi Omicron Pi Rho";
const GREEK_UPPER_TAIL = "Sigma Tau Upsilon Phi Chi Psi Omega";
const GREEK_LOWER =
    "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho " +
    "sigmaf sigma tau upsilon phi chi psi omega";

const OTHERS = {
    quot: 34, amp: 38, apos: 39, lt: 60, gt: 62,
    OElig: 338, oelig: 339, Scaron: 352, scaron: 353, Yuml: 376, fnof: 402, circ: 710, tilde: 732,
    thetasym: 977, upsih: 978, piv: 982,
    ensp: 8194, emsp: 8195, thinsp: 8201, zwnj: 8204, zwj: 8205, lrm: 8206, rlm: 8207,
    ndash: 8211, mdash: 8212, lsquo: 8216, rsquo: 8217, sbquo: 8218, ldquo: 8220, rdquo: 8221,
    bdquo: 8222, dagger: 8224, Dagger: 8225, bull: 8226, hellip: 8230, permil: 8240, prime: 8242,
    Prime: 8243, lsaquo: 8249, rsaquo: 8250, oline: 8254, frasl: 8260, euro: 8364, image: 8465,
    weierp: 8472, real: 8476, trade: 8482, alefsym: 8501,
    larr: 8592, uarr: 8593, rarr: 8594, darr: 8595, harr: 8596, crarr: 8629,
    lArr: 8656, uArr: 8657, rArr: 8658, dArr: 8659, hArr: 8660,
    forall: 8704, part: 8706, exist: 8707, empty: 8709, nabla: 8711, isin: 8712, notin: 8713,
    ni: 8715, prod: 8719, sum: 8721, minus: 8722, lowast: 8727, radic: 8730, prop: 8733,
    infin: 8734, ang: 8736, and: 8743, or: 8744, cap: 8745, cup: 8746, int: 8747, there4: 8756,
    sim: 8764, cong: 8773, asymp: 8776, ne: 8800, equiv: 8801, le: 8804, ge: 8805, sub: 8834,
    sup: 8835, nsub: 8836, sube: 8838, supe: 8839, oplus: 8853, otimes: 8855, perp: 8869,
    sdot: 8901, lceil: 8968, rceil: 8969, lfloor: 8970, rfloor: 8971, lang: 9001, rang: 9002,
    loz: 9674, spades: 9824, clubs: 9827, hearts: 9829, diams: 9830, check: 10003,
};

export const NAMED = (() => {
    const map = new Map();
    LATIN1.split(" ").forEach((name, i) => map.set(name, 160 + i));
    GREEK_UPPER.split(" ").forEach((name, i) => map.set(name, 913 + i));
    GREEK_UPPER_TAIL.split(" ").forEach((name, i) => map.set(name, 931 + i));
    GREEK_LOWER.split(" ").forEach((name, i) => map.set(name, 945 + i));
    for (const [name, code] of Object.entries(OTHERS)) {
        map.set(name, code);
    }
    return map;
})();

const BY_CODE = (() => {
    const map = new Map();
    for (const [name, code] of NAMED) {
        if (!map.has(code)) {
            map.set(code, name);
        }
    }
    return map;
})();

// HTML numeric references in 0x80-0x9F are read as Windows-1252 (WHATWG spec).
const C1_REMAP = {
    0x80: 0x20ac, 0x82: 0x201a, 0x83: 0x0192, 0x84: 0x201e, 0x85: 0x2026, 0x86: 0x2020,
    0x87: 0x2021, 0x88: 0x02c6, 0x89: 0x2030, 0x8a: 0x0160, 0x8b: 0x2039, 0x8c: 0x0152,
    0x8e: 0x017d, 0x91: 0x2018, 0x92: 0x2019, 0x93: 0x201c, 0x94: 0x201d, 0x95: 0x2022,
    0x96: 0x2013, 0x97: 0x2014, 0x98: 0x02dc, 0x99: 0x2122, 0x9a: 0x0161, 0x9b: 0x203a,
    0x9c: 0x0153, 0x9e: 0x017e, 0x9f: 0x0178,
};

const BASIC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function encodeEntities(text, { mode = "basic" } = {}) {
    let out = "";
    for (const char of text) {
        if (BASIC[char]) {
            out += BASIC[char];
            continue;
        }
        const code = char.codePointAt(0);
        if (code < 128 || mode === "basic") {
            out += char;
        } else if (mode === "named" && BY_CODE.has(code)) {
            out += `&${BY_CODE.get(code)};`;
        } else if (mode === "decimal") {
            out += `&#${code};`;
        } else {
            out += `&#x${code.toString(16).toUpperCase()};`;
        }
    }
    return out;
}

function fromCode(code) {
    if (C1_REMAP[code]) {
        return String.fromCodePoint(C1_REMAP[code]);
    }
    if (code === 0 || code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff)) {
        return "�";
    }
    return String.fromCodePoint(code);
}

export function decodeEntities(text) {
    return text.replace(
        /&(?:#(\d{1,8})|#[xX]([0-9a-fA-F]{1,7})|([A-Za-z][A-Za-z0-9]{1,31}));/g,
        (whole, decimal, hex, name) => {
            if (decimal !== undefined) {
                return fromCode(parseInt(decimal, 10));
            }
            if (hex !== undefined) {
                return fromCode(parseInt(hex, 16));
            }
            return NAMED.has(name) ? String.fromCodePoint(NAMED.get(name)) : whole;
        }
    );
}

export function encodeUrl(text, { mode = "component", spaceAsPlus = false } = {}) {
    let out = mode === "uri" ? encodeURI(text) : encodeURIComponent(text);
    if (spaceAsPlus) {
        out = out.replace(/%20/g, "+");
    }
    return out;
}

export function decodeUrl(text, { plusAsSpace = false } = {}) {
    const source = plusAsSpace ? text.replace(/\+/g, " ") : text;
    try {
        return decodeURIComponent(source);
    } catch {
        throw new Error("Malformed percent-encoding: a % must be followed by two hex digits forming valid UTF-8.");
    }
}

export function parseUrl(input) {
    const text = String(input).trim();
    if (!text) {
        throw new Error("Enter a URL to parse.");
    }
    let url;
    let assumedScheme = false;
    try {
        url = new URL(text);
    } catch {
        if (/^[\w-]+(\.[\w-]+)+(:\d+)?([/?#].*)?$/.test(text) || text.startsWith("//")) {
            url = new URL(text.startsWith("//") ? `https:${text}` : `https://${text}`);
            assumedScheme = true;
        } else {
            throw new Error("That does not look like a valid absolute URL (for example https://example.com/path?q=1).");
        }
    }
    const params = [];
    for (const [key, value] of url.searchParams) {
        params.push([key, value]);
    }
    return {
        assumedScheme,
        href: url.href,
        protocol: url.protocol,
        username: decodeSafe(url.username),
        password: decodeSafe(url.password),
        hostname: url.hostname,
        port: url.port,
        origin: url.origin,
        pathname: url.pathname,
        decodedPath: decodeSafe(url.pathname),
        search: url.search,
        hash: url.hash,
        params,
    };
}

function decodeSafe(text) {
    try {
        return decodeURIComponent(text);
    } catch {
        return text;
    }
}

export function paramsToObject(params) {
    // Null prototype so a "__proto__" parameter is stored as data.
    const out = Object.create(null);
    for (const [key, value] of params) {
        if (Object.prototype.hasOwnProperty.call(out, key)) {
            out[key] = [].concat(out[key], value);
        } else {
            out[key] = value;
        }
    }
    return out;
}

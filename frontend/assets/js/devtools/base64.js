function bytesToBinary(bytes) {
    let binary = "";
    for (let i = 0; i < bytes.length; i += 0x8000) {
        binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    }
    return binary;
}

export function bytesToBase64(bytes, { urlSafe = false, padding = true } = {}) {
    let out = btoa(bytesToBinary(bytes));
    if (urlSafe) {
        out = out.replace(/\+/g, "-").replace(/\//g, "_");
    }
    if (!padding) {
        out = out.replace(/=+$/, "");
    }
    return out;
}

export function encodeBase64(text, { urlSafe = false, padding = !urlSafe } = {}) {
    return bytesToBase64(new TextEncoder().encode(text), { urlSafe, padding });
}

export function base64ToBytes(input) {
    let text = String(input).trim();
    const dataUri = text.match(/^data:[^,]*;base64,/i);
    if (dataUri) {
        text = text.slice(dataUri[0].length);
    }
    text = text.replace(/\s+/g, "").replace(/-/g, "+").replace(/_/g, "/");
    if (!/^[A-Za-z0-9+/]*={0,2}$/.test(text)) {
        throw new Error("Input contains characters that are not valid Base64.");
    }
    text = text.replace(/=+$/, "");
    if (text.length % 4 === 1) {
        throw new Error("Base64 input has an invalid length.");
    }
    text += "=".repeat((4 - (text.length % 4)) % 4);
    const binary = atob(text);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
}

export function decodeBase64(input) {
    const bytes = base64ToBytes(input);
    try {
        return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    } catch {
        throw new Error(
            "Decoded bytes are not valid UTF-8 text. The input is probably binary data (an image or file)."
        );
    }
}

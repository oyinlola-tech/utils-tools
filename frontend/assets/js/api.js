import { API_ORIGIN } from "./config.js";
import { relayFetch } from "./relay.js";

const API_BASE_URL = `${API_ORIGIN}/api/v1`;

// JSON endpoints that can outlast the host's request limit; uploads
// always go through the relay.
const SLOW_PATHS = ["/tools/video/", "/tools/text/text-to-speech"];

const CAPABILITIES_KEY = "utils-tool:capabilities";
const CAPABILITIES_FRESH_MS = 10 * 60 * 1000;

/**
 * The backend returns root-relative links (download_url,
 * download_all_url). When the API lives on another origin they have to
 * point there, otherwise images and downloads resolve against the page.
 */
function resolveApiLinks(value) {
    if (!API_ORIGIN || value === null || typeof value !== "object") {
        return value;
    }
    for (const [key, item] of Object.entries(value)) {
        if (typeof item === "string") {
            if (/(^|_)url$/.test(key) && item.startsWith("/api/")) {
                value[key] = `${API_ORIGIN}${item}`;
            }
        } else {
            resolveApiLinks(item);
        }
    }
    return value;
}

async function parseJsonResponse(response) {
    const text = await response.text();
    if (!text) {
        return null;
    }
    try {
        return resolveApiLinks(JSON.parse(text));
    } catch {
        return null;
    }
}

function extractErrorMessage(data, fallback) {
    if (data && data.error && data.error.message) {
        return data.error.message;
    }
    if (data && data.detail) {
        return data.detail;
    }
    return fallback;
}

/**
 * True for errors caused by the user's input (bad JSON, wrong file type,
 * encrypted PDF...). Those should be shown inline next to the form, not
 * by navigating away to a full-page error screen that loses the input.
 */
export function isInputError(error) {
    const status = Number(error && error.status);
    return status >= 400 && status < 500 && status !== 408 && status !== 429;
}

function apiError(response, data, fallback) {
    const error = new Error(extractErrorMessage(data, fallback));
    error.status = response.status;
    return error;
}

async function usesRelay(url, options) {
    if (options.method !== "POST") {
        return false;
    }
    const upload = options.body instanceof FormData;
    if (!upload && !SLOW_PATHS.some((path) => url.includes(path))) {
        return false;
    }
    const capabilities = await getCapabilities().catch(() => null);
    return Boolean(capabilities && capabilities.system && capabilities.system.relay);
}

async function safeFetch(url, options = {}) {
    const relayed = await usesRelay(url, options);
    const controller = new AbortController();
    const timeout = options.timeout || 0;
    let timeoutId;
    if (timeout > 0) {
        timeoutId = setTimeout(() => controller.abort(), timeout);
    }
    try {
        const send = relayed ? relayFetch : fetch;
        const response = await send(url, {
            ...options,
            signal: controller.signal,
        });
        return response;
    } catch (error) {
        if (error.name === "AbortError") {
            throw new Error("Request timed out. Please check your connection and try again.");
        }
        if (!navigator.onLine) {
            throw new Error("You appear to be offline. Please check your internet connection.");
        }
        throw new Error("Network error. Please try again.");
    } finally {
        if (timeoutId) clearTimeout(timeoutId);
    }
}

export async function startBackgroundRemoval(file, outputFormat = "webp") {
    const formData = new FormData();
    formData.append("file", file);

    const params = new URLSearchParams();
    params.set("output_format", outputFormat);

    const response = await safeFetch(
        `${API_BASE_URL}/background/start?${params.toString()}`,
        {
            method: "POST",
            body: formData,
        }
    );

    const data = await parseJsonResponse(response);
    if (!response.ok) {
        throw apiError(response, data, "Unable to process image.");
    }
    return data;
}

export async function startBatchCompression({
    files,
    imageOutputFormat = "webp",
    compressionPreset = "balanced",
    maxDimension = null,
    targetSizeKb = null,
    stripMetadata = true,
    quality = null,
}) {
    const formData = new FormData();
    for (const file of files) {
        formData.append("files", file);
    }

    const params = new URLSearchParams();
    params.set("image_output_format", imageOutputFormat);
    params.set("compression_preset", compressionPreset);

    if (quality !== null && quality !== "") {
        params.set("quality", String(quality));
    }

    if (maxDimension !== null && maxDimension !== "") {
        params.set("max_dimension", String(maxDimension));
    }

    if (targetSizeKb !== null && targetSizeKb !== "") {
        params.set("target_size_kb", String(targetSizeKb));
    }

    params.set("strip_metadata", String(stripMetadata));

    const response = await safeFetch(
        `${API_BASE_URL}/compression/batch/start?${params.toString()}`,
        {
            method: "POST",
            body: formData,
        }
    );

    const data = await parseJsonResponse(response);
    if (!response.ok) {
        throw apiError(response, data, "Unable to compress files.");
    }
    return data;
}

export async function startImageCompression({
    files,
    outputFormat = "auto",
    quality = null,
    compressionPreset = "balanced",
    maxDimension = null,
    targetSize = null,
    removeMetadata = true,
}) {
    const formData = new FormData();
    for (const file of files) {
        formData.append("files", file);
    }

    if (quality !== null && quality !== "") {
        formData.append("quality", String(quality));
    }
    formData.append("output_format", outputFormat);
    formData.append("compression_preset", compressionPreset);
    formData.append("remove_metadata", String(removeMetadata));

    if (maxDimension !== null && maxDimension !== "") {
        formData.append("max_dimension", String(maxDimension));
    }

    if (targetSize !== null && targetSize !== "") {
        formData.append("target_size", String(targetSize));
    }

    const response = await safeFetch(
        `${API_BASE_URL}/images/compress`,
        {
            method: "POST",
            body: formData,
        }
    );

    const data = await parseJsonResponse(response);
    if (!response.ok) {
        throw apiError(response, data, "Unable to compress images.");
    }
    return data;
}

export async function cancelJob(jobId) {
    const response = await safeFetch(`${API_BASE_URL}/jobs/${jobId}`, {
        method: "DELETE",
    });
    const data = await parseJsonResponse(response);
    if (!response.ok) {
        throw apiError(response, data, "Unable to cancel job.");
    }
    return data;
}

export async function getJob(jobId) {
    const response = await safeFetch(`${API_BASE_URL}/jobs/${jobId}`);
    const data = await parseJsonResponse(response);
    if (!response.ok) {
        throw apiError(response, data, "Unable to load job.");
    }
    return data;
}

async function fetchCapabilities() {
    const response = await safeFetch(`${API_BASE_URL}/capabilities`);
    const data = await parseJsonResponse(response);
    if (!response.ok) {
        throw apiError(response, data, "Unable to load capabilities.");
    }
    try {
        sessionStorage.setItem(CAPABILITIES_KEY, JSON.stringify({ at: Date.now(), data }));
    } catch {
        // Storage can be full or blocked; the page works without it.
    }
    return data;
}

function storedCapabilities() {
    try {
        const stored = JSON.parse(sessionStorage.getItem(CAPABILITIES_KEY));
        if (stored && Date.now() - stored.at < CAPABILITIES_FRESH_MS) {
            return stored.data;
        }
    } catch {
        // Unreadable or blocked storage is the same as none.
    }
    return null;
}

let capabilities = null;

/**
 * Every page needs the capabilities before it can enable anything, so a
 * recent copy is served at once and refreshed behind it for the next
 * page, rather than holding each page up for a round trip.
 */
export function getCapabilities() {
    if (!capabilities) {
        const stored = storedCapabilities();
        const fetched = fetchCapabilities();
        if (stored) {
            fetched.catch(() => {});
            capabilities = Promise.resolve(stored);
        } else {
            capabilities = fetched.catch((error) => {
                capabilities = null;
                throw error;
            });
        }
    }
    return capabilities;
}


export async function apiGet(path) {
    const response = await safeFetch(`${API_BASE_URL}${path}`);
    const data = await parseJsonResponse(response);
    if (!response.ok) {
        throw apiError(response, data, "Request failed.");
    }
    return data;
}

export async function apiJsonPost(path, bodyPayload = {}) {
    const response = await safeFetch(`${API_BASE_URL}${path}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(bodyPayload),
    });
    const data = await parseJsonResponse(response);
    if (!response.ok) {
        throw apiError(response, data, "Request failed.");
    }
    return data;
}

function buildFormData(files = [], fields = {}) {
    const formData = new FormData();
    for (const item of files) {
        if (item instanceof File) {
            formData.append("file", item);
        } else {
            formData.append(item.name, item.file);
        }
    }
    for (const [key, value] of Object.entries(fields)) {
        if (value !== null && value !== undefined && value !== "") {
            formData.append(key, String(value));
        }
    }
    return formData;
}


export async function apiUpload(path, { files = [], fields = {} } = {}) {
    const formData = buildFormData(files, fields);
    const response = await safeFetch(`${API_BASE_URL}${path}`, {
        method: "POST",
        body: formData,
    });
    const data = await parseJsonResponse(response);
    if (!response.ok) {
        throw apiError(response, data, "Request failed.");
    }
    return data;
}


export async function apiDownload(path, { files = [], fields = {} } = {}) {
    const formData = buildFormData(files, fields);
    const response = await safeFetch(`${API_BASE_URL}${path}`, {
        method: "POST",
        body: formData,
    });
    if (!response.ok) {
        const data = await parseJsonResponse(response);
        throw apiError(response, data, "Request failed.");
    }
    const blob = await response.blob();
    let filename = "download";
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?([^";]+)"?/);
    if (match) {
        filename = match[1];
    }
    return { blob, filename, contentType: response.headers.get("Content-Type") || "" };
}

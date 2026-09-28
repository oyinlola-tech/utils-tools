/**
 * Sends a request through the backend's relay instead of directly.
 *
 * The host cuts any request that lasts longer than about 30 seconds, so a
 * large upload on a slow connection, or a tool that takes a while, would
 * fail however it was sent. Through the relay the body goes up in short
 * chunks, the tool runs detached from any connection, and the response
 * is collected once it is ready. relayFetch() resolves to a Response, as
 * fetch() would have for the same request.
 */
import { API_ORIGIN } from "./config.js";

const RELAY_URL = `${API_ORIGIN}/api/v1/relay`;

const KB = 1024;
const MB = 1024 * KB;
// Bodies up to this size travel with the run request itself.
const INLINE_BYTES = 512 * KB;
const FIRST_CHUNK_BYTES = 512 * KB;
const MIN_CHUNK_BYTES = 256 * KB;
const MAX_CHUNK_BYTES = 8 * MB;
// Chunks are sized to take about this long on the connection at hand:
// well inside the host's limit, without a request per few kilobytes.
const CHUNK_SECONDS = 5;
const PARALLEL_UPLOADS = 3;
const ATTEMPTS = 6;
// A chunk is sized to take seconds; one still going after this has stalled
// and is about to be cut by the host anyway.
const CHUNK_TIMEOUT_MS = 25 * 1000;
// How long the server may hold a request open waiting for the result.
const WAIT_SECONDS = 15;
const GIVE_UP_AFTER_MS = 30 * 60 * 1000;
// Consecutive requests that may fail before the connection is given up on.
const LOST_LIMIT = 20;

const pause = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function newSessionId() {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function quoted(value) {
    return String(value).replace(/"/g, "%22").replace(/\r/g, "%0D").replace(/\n/g, "%0A");
}

/**
 * Builds the multipart body by hand so it can be sliced: a Blob made of
 * File parts refers to the files on disk rather than copying them.
 */
function encodeMultipart(formData) {
    const boundary = `----utils-tool-${newSessionId()}`;
    const parts = [];
    for (const [name, value] of formData.entries()) {
        let header = `--${boundary}\r\nContent-Disposition: form-data; name="${quoted(name)}"`;
        if (value instanceof Blob) {
            header += `; filename="${quoted(value.name || "blob")}"`;
            header += `\r\nContent-Type: ${value.type || "application/octet-stream"}`;
        }
        parts.push(`${header}\r\n\r\n`, value, "\r\n");
    }
    parts.push(`--${boundary}--\r\n`);
    return {
        body: new Blob(parts),
        type: `multipart/form-data; boundary=${boundary}`,
    };
}

function encodeBody(options) {
    if (options.body instanceof FormData) {
        return encodeMultipart(options.body);
    }
    const headers = new Headers(options.headers || {});
    return {
        body: new Blob([options.body ?? ""]),
        type: headers.get("Content-Type") || "application/octet-stream",
    };
}

/** Retries what a dropped connection breaks; an answer is an answer. */
async function attempt(send, signal) {
    for (let tries = 1; ; tries += 1) {
        try {
            return await send();
        } catch (error) {
            if (signal.aborted || tries >= ATTEMPTS || error.name === "TimeoutError") {
                throw error;
            }
            await pause(Math.min(500 * 2 ** (tries - 1), 8000));
        }
    }
}

async function sendChunk(url, chunk, signal) {
    const stalled = new AbortController();
    const timer = setTimeout(() => stalled.abort(), CHUNK_TIMEOUT_MS);
    const cancel = () => stalled.abort();
    signal.addEventListener("abort", cancel, { once: true });
    try {
        return await fetch(url, { method: "POST", body: chunk, signal: stalled.signal });
    } catch (error) {
        if (!signal.aborted && stalled.signal.aborted) {
            throw new DOMException("The chunk stalled.", "TimeoutError");
        }
        throw error;
    } finally {
        clearTimeout(timer);
        signal.removeEventListener("abort", cancel);
    }
}

async function uploadChunks(session, body, type, signal) {
    const size = body.size;
    let chunkBytes = FIRST_CHUNK_BYTES;
    let next = 0;
    let refusal = null;
    // Ranges to send again in smaller pieces, ahead of fresh ones.
    const again = [];

    const take = () => {
        if (again.length) {
            return again.shift();
        }
        if (next >= size) {
            return null;
        }
        const start = next;
        next = Math.min(size, start + chunkBytes);
        return [start, next];
    };

    const upload = async ([start, end]) => {
        const query = new URLSearchParams({ offset: start, size, type });
        const url = `${RELAY_URL}/${session}/chunk?${query}`;
        const started = performance.now();
        let response;
        try {
            response = await attempt(() => sendChunk(url, body.slice(start, end), signal), signal);
        } catch (error) {
            if (error.name !== "TimeoutError" || end - start <= MIN_CHUNK_BYTES) {
                throw error;
            }
            // The connection got slower than this chunk was sized for.
            chunkBytes = MIN_CHUNK_BYTES;
            for (let from = start; from < end; from += MIN_CHUNK_BYTES) {
                again.push([from, Math.min(end, from + MIN_CHUNK_BYTES)]);
            }
            return;
        }
        if (!response.ok) {
            refusal = refusal || response;
            return;
        }
        const seconds = Math.max((performance.now() - started) / 1000, 0.05);
        const fitting = ((end - start) / seconds) * CHUNK_SECONDS;
        chunkBytes = Math.round(Math.min(MAX_CHUNK_BYTES, Math.max(MIN_CHUNK_BYTES, fitting)));
    };

    const worker = async () => {
        for (let range = take(); range && !refusal; range = take()) {
            await upload(range);
        }
    };

    // The first chunk goes alone: it opens the upload on the server and
    // measures the connection before the parallel ones are sized.
    await upload(take());
    await Promise.all(Array.from({ length: PARALLEL_UPLOADS }, worker));
    return refusal;
}

async function neverStarted(response) {
    if (response.status !== 404) {
        return false;
    }
    const answer = await response.clone().json().catch(() => null);
    return Boolean(answer && answer.error && answer.error.code === "RELAY_NOT_STARTED");
}

async function collect(session, signal, run) {
    const deadline = Date.now() + GIVE_UP_AFTER_MS;
    let response = await run().catch(() => null);
    let lost = 0;
    while (Date.now() < deadline && !signal.aborted && lost <= LOST_LIMIT) {
        if (!response) {
            // The connection dropped; the request may well be running.
            lost += 1;
            await pause(Math.min(500 * lost, 3000));
        } else if (response.status === 202) {
            lost = 0;
        } else if (await neverStarted(response)) {
            lost += 1;
            response = await run().catch(() => null);
            continue;
        } else {
            return response;
        }
        response = await fetch(`${RELAY_URL}/${session}?wait=${WAIT_SECONDS}`, { signal }).catch(
            () => null
        );
    }
    throw new Error("The request did not finish.");
}

export async function relayFetch(url, options = {}) {
    const signal = options.signal || new AbortController().signal;
    const session = newSessionId();
    const { body, type } = encodeBody(options);
    const target = new URL(url, window.location.href);
    const query = new URLSearchParams({
        path: `${target.pathname}${target.search}`,
        wait: WAIT_SECONDS,
    });
    const runUrl = `${RELAY_URL}/${session}/run?${query}`;

    if (body.size <= INLINE_BYTES) {
        return collect(session, signal, () =>
            fetch(runUrl, {
                method: "POST",
                body,
                headers: { "Content-Type": type },
                signal,
            })
        );
    }

    const refusal = await uploadChunks(session, body, type, signal);
    if (refusal) {
        return refusal;
    }
    return collect(session, signal, () => fetch(runUrl, { method: "POST", signal }));
}

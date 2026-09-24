import { runRegex } from "./regex.js";

self.addEventListener("message", (event) => {
    const { id, ...job } = event.data;
    try {
        self.postMessage({ id, ...runRegex(job) });
    } catch (error) {
        self.postMessage({ id, error: error.message, matches: [], truncated: false, replaced: null });
    }
});

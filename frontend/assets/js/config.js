/**
 * Where the API lives for each host that serves these pages.
 *
 * Hosts not listed here use the same origin: local development, where
 * FastAPI serves both the pages and the API, and Vercel previews, where
 * /api is proxied to the backend.
 */
const API_ORIGINS = {
    "tools.oyinlola.site": "https://tools.telente.site",
};

export const API_ORIGIN = API_ORIGINS[window.location.hostname] || "";

import { getCapabilities } from "./api.js";

let cachePromise = null;
let cache = null;

export async function loadCapabilities() {
    if (cache) {
        return cache;
    }
    if (!cachePromise) {
        cachePromise = getCapabilities()
            .then((data) => {
                cache = data;
                return data;
            })
            .catch((error) => {
                cachePromise = null;
                throw error;
            });
    }
    return cachePromise;
}

export function getTool(toolId) {
    if (!cache) {
        return null;
    }
    return cache.tools.find((tool) => tool.id === toolId) || null;
}

export function isAvailable(toolId) {
    const tool = getTool(toolId);
    return Boolean(tool && tool.status === "available");
}

export function availableTools() {
    if (!cache) {
        return [];
    }
    return cache.tools.filter((tool) => tool.status === "available");
}

export function toolsByCategory(category) {
    if (!cache) {
        return [];
    }
    return cache.tools.filter((tool) => tool.category === category);
}

export function getAppInfo() {
    return cache ? cache.app : null;
}

export const CATEGORY_META = {
    image: {
        title: "Image tools",
        description: "Remove backgrounds, compress, convert, resize, crop, edit and more.",
    },
    pdf: {
        title: "PDF tools",
        description: "Compress, merge, split, convert and reorganize PDF documents.",
    },
    file: {
        title: "File tools",
        description: "Analyze files, package archives and find duplicates.",
    },
    developer: {
        title: "Developer tools",
        description: "Favicons, SVG optimization, SVG generation, Base64, QR codes and barcodes.",
    },
    text: {
        title: "Text tools",
        description: "Count words, compare text, change case and turn text into speech.",
    },
    utility: {
        title: "Utility tools",
        description: "Social media presets and screenshot beautification.",
    },
};

export const CATEGORY_ORDER = ["image", "pdf", "file", "developer", "text", "utility"];

// Short file-type labels. The tag colour (--tag-<category>) encodes what
// kind of file a tool works on, everywhere a tool is listed.
export const CATEGORY_TAG = {
    image: "IMG",
    pdf: "PDF",
    file: "FILE",
    developer: "DEV",
    text: "TXT",
    utility: "UTIL",
};

export function tagHtml(category) {
    const label = CATEGORY_TAG[category] || "TOOL";
    return `<span class="file-tag" data-category="${category}">${label}</span>`;
}

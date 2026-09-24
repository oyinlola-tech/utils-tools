import { availableTools, loadCapabilities } from "../capabilities.js";

loadCapabilities()
    .then(() => {
        const count = availableTools().length;
        document.querySelectorAll("[data-tool-count]").forEach((el) => {
            el.textContent = String(count);
        });
    })
    .catch(() => {});

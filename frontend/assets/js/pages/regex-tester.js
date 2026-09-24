import { initToolPage } from "./tool-kit.js";
import { runRegex, segments, normalizeFlags, captureGroupNames } from "../devtools/regex.js";
import { wireCopy, debounce, clear, el } from "../devtools/dom.js";

const kit = await initToolPage("regex-tester");

const TIMEOUT_MS = 1500;
const MATCH_LIMIT = 1000;

if (kit.available) {
    const pattern = document.querySelector("#rx-pattern");
    const text = document.querySelector("#rx-text");
    const replace = document.querySelector("#rx-replace");
    const replaced = document.querySelector("#rx-replaced");
    const highlight = document.querySelector("#rx-highlight");
    const summary = document.querySelector("#rx-summary");
    const matchesHost = document.querySelector("#rx-matches");
    const flagInputs = [...document.querySelectorAll("[id^=rx-flag-]")];

    let lastResult = { matches: [] };
    let worker = null;
    let pending = null;
    let jobId = 0;

    function flags() {
        return normalizeFlags(flagInputs.filter((input) => input.checked).map((input) => input.id.slice(-1)).join(""));
    }

    // Patterns run in a worker so catastrophic backtracking can be killed
    // instead of freezing the tab.
    function startWorker() {
        try {
            worker = new Worker(new URL("../devtools/regex-worker.js", import.meta.url), { type: "module" });
            worker.addEventListener("message", (event) => {
                if (pending && event.data.id === pending.id) {
                    clearTimeout(pending.timer);
                    const resolve = pending.resolve;
                    pending = null;
                    resolve(event.data);
                }
            });
        } catch {
            worker = null;
        }
    }

    function execute(job) {
        if (!worker) {
            return Promise.resolve(runRegex(job));
        }
        if (pending) {
            clearTimeout(pending.timer);
            pending.resolve(null);
            pending = null;
            worker.terminate();
            startWorker();
        }
        return new Promise((resolve) => {
            const id = ++jobId;
            const timer = setTimeout(() => {
                pending = null;
                worker.terminate();
                startWorker();
                resolve({
                    error: `The pattern took longer than ${TIMEOUT_MS / 1000}s and was stopped. It probably backtracks catastrophically; try a more specific pattern.`,
                    matches: [],
                    truncated: false,
                    replaced: null,
                });
            }, TIMEOUT_MS);
            pending = { id, timer, resolve };
            worker.postMessage({ id, ...job });
        });
    }

    function renderHighlight(result) {
        clear(highlight);
        const parts = segments(text.value, result.matches);
        for (const part of parts) {
            if (part.match >= 0) {
                highlight.appendChild(el("mark", { title: `Match ${part.match + 1}`, text: part.text }));
            } else {
                highlight.appendChild(document.createTextNode(part.text));
            }
        }
    }

    function renderTable(result) {
        clear(matchesHost);
        if (!result.matches.length) {
            return;
        }
        const groupCount = Math.max(...result.matches.map((m) => m.groups.length));
        const namedByIndex = captureGroupNames(pattern.value);
        const head = [el("th", { scope: "col", text: "#" }), el("th", { scope: "col", text: "Match" }), el("th", { scope: "col", text: "Index" })];
        for (let i = 0; i < groupCount; i += 1) {
            head.push(el("th", { scope: "col", text: namedByIndex[i] ? `Group ${i + 1} (${namedByIndex[i]})` : `Group ${i + 1}` }));
        }
        const body = el("tbody");
        result.matches.slice(0, 200).forEach((match, index) => {
            const cells = [
                el("td", { text: String(index + 1) }),
                el("td", {}, [el("code", { text: match.text || "(empty)" })]),
                el("td", { text: `${match.index}-${match.end}` }),
            ];
            for (let i = 0; i < groupCount; i += 1) {
                const value = match.groups[i];
                cells.push(el("td", {}, [el("code", { text: value === undefined ? "(no match)" : value })]));
            }
            body.appendChild(el("tr", {}, cells));
        });
        matchesHost.appendChild(
            el("table", { className: "analysis-table" }, [
                el("caption", { className: "visually-hidden", text: "Match details" }),
                el("thead", {}, [el("tr", {}, head)]),
                body,
            ])
        );
    }

    async function run() {
        const result = await execute({
            pattern: pattern.value,
            flags: flags(),
            text: text.value,
            replacement: replace.value,
            limit: MATCH_LIMIT,
        });
        if (!result) {
            return;
        }
        lastResult = result;
        if (result.error) {
            pattern.setAttribute("aria-invalid", "true");
            kit.banner.show(result.error);
            summary.textContent = "";
            clear(highlight);
            highlight.appendChild(document.createTextNode(text.value));
            clear(matchesHost);
            replaced.value = "";
            return;
        }
        pattern.removeAttribute("aria-invalid");
        kit.banner.hide();
        const count = result.matches.length;
        summary.textContent =
            count === 0
                ? "No matches."
                : `${count}${result.truncated ? "+" : ""} match${count === 1 ? "" : "es"}` +
                  (count > 200 ? " (table shows the first 200)" : "") +
                  (flags().includes("g") ? "." : ". Turn on the g flag to find every match.");
        renderHighlight(result);
        renderTable(result);
        replaced.value = result.replaced ?? "";
    }

    startWorker();
    const scheduled = debounce(run, 150);
    for (const input of [pattern, text, replace]) {
        input.addEventListener("input", scheduled);
    }
    for (const input of flagInputs) {
        input.addEventListener("change", run);
    }
    wireCopy(document.querySelector("#rx-copy-matches"), () => lastResult.matches.map((m) => m.text).join("\n"));
    wireCopy(document.querySelector("#rx-copy-literal"), () => `/${pattern.value.replace(/(^|[^\\])\//g, "$1\\/")}/${flags()}`);
    wireCopy(document.querySelector("#rx-copy-replaced"), () => replaced.value);

    run();
}

import { initToolPage } from "./tool-kit.js";
import { parseCron, describeCron, nextRuns, EXAMPLES } from "../devtools/cron.js";
import { wireCopy, debounce, clear, el } from "../devtools/dom.js";
import { relativeTime } from "../devtools/timestamp.js";

const kit = await initToolPage("cron-parser");

const FIELD_LABELS = {
    second: "Second",
    minute: "Minute",
    hour: "Hour",
    dom: "Day of month",
    month: "Month",
    dow: "Day of week",
};
const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function compress(values, name) {
    const sorted = [...values].sort((a, b) => a - b);
    const label = (v) => (name === "dow" ? DAY_NAMES[v] : name === "month" ? MONTH_NAMES[v - 1] : String(v));
    const ranges = [];
    let start = sorted[0];
    let prev = sorted[0];
    for (const value of sorted.slice(1).concat([Infinity])) {
        if (value === prev + 1) {
            prev = value;
            continue;
        }
        ranges.push(start === prev ? label(start) : `${label(start)}-${label(prev)}`);
        start = value;
        prev = value;
    }
    return ranges.join(", ");
}

if (kit.available) {
    const input = document.querySelector("#cron-input");
    const examples = document.querySelector("#cron-examples");
    const zone = document.querySelector("#cron-zone");
    const count = document.querySelector("#cron-count");
    const description = document.querySelector("#cron-description");
    const fieldsHost = document.querySelector("#cron-fields");
    const runsList = document.querySelector("#cron-runs");
    let runTexts = [];

    const localZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (localZone) {
        zone.options[0].textContent = `Local time (${localZone})`;
    }
    for (const [expression, label] of EXAMPLES) {
        examples.appendChild(el("option", { value: expression, text: `${label}: ${expression}` }));
    }

    function formatRun(date, utc) {
        return new Intl.DateTimeFormat(undefined, {
            weekday: "short",
            year: "numeric",
            month: "short",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            timeZone: utc ? "UTC" : undefined,
            timeZoneName: "short",
        }).format(date);
    }

    function explain() {
        clear(fieldsHost);
        clear(runsList);
        runTexts = [];
        input.removeAttribute("aria-invalid");
        let schedule;
        try {
            schedule = parseCron(input.value);
        } catch (error) {
            input.setAttribute("aria-invalid", "true");
            description.textContent = "";
            kit.banner.show(error.message);
            return;
        }
        kit.banner.hide();
        description.textContent = describeCron(schedule);

        const names = schedule.hasSeconds
            ? ["second", "minute", "hour", "dom", "month", "dow"]
            : ["minute", "hour", "dom", "month", "dow"];
        const body = el("tbody");
        for (const name of names) {
            body.appendChild(
                el("tr", {}, [
                    el("th", { scope: "row", text: FIELD_LABELS[name] }),
                    el("td", {}, [el("code", { text: schedule[name].raw })]),
                    el("td", { text: compress(schedule[name].values, name) }),
                ])
            );
        }
        fieldsHost.appendChild(
            el("table", { className: "analysis-table" }, [
                el("caption", { className: "visually-hidden", text: "Cron fields" }),
                el("thead", {}, [
                    el("tr", {}, [
                        el("th", { scope: "col", text: "Field" }),
                        el("th", { scope: "col", text: "Value" }),
                        el("th", { scope: "col", text: "Matches" }),
                    ]),
                ]),
                body,
            ])
        );

        const utc = zone.value === "utc";
        const total = Math.min(25, Math.max(1, Math.floor(Number(count.value)) || 5));
        const runs = nextRuns(schedule, new Date(), total, { utc });
        if (!runs.length) {
            runsList.appendChild(el("li", { text: "This schedule never runs (for example, 30 February)." }));
            return;
        }
        const now = Date.now();
        for (const run of runs) {
            const text = formatRun(run, utc);
            runTexts.push(`${text} (${run.toISOString()})`);
            runsList.appendChild(
                el("li", {}, [el("time", { datetime: run.toISOString(), text }), ` · ${relativeTime(run.getTime(), now)}`])
            );
        }
    }

    input.addEventListener("input", debounce(explain, 150));
    zone.addEventListener("change", explain);
    count.addEventListener("input", debounce(explain, 200));
    examples.addEventListener("change", () => {
        if (examples.value) {
            input.value = examples.value;
            explain();
        }
    });
    wireCopy(document.querySelector("#cron-copy-description"), () => description.textContent);
    wireCopy(document.querySelector("#cron-copy-runs"), () => runTexts.join("\n"));

    explain();
}

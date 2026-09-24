const MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"];
const DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];

const FIELDS = {
    second: { min: 0, max: 59, unit: "second" },
    minute: { min: 0, max: 59, unit: "minute" },
    hour: { min: 0, max: 23, unit: "hour" },
    dom: { min: 1, max: 31, unit: "day" },
    month: { min: 1, max: 12, unit: "month", names: MONTHS.map((m) => m.slice(0, 3)), offset: 1 },
    dow: { min: 0, max: 7, unit: "day of the week", names: DAYS.map((d) => d.slice(0, 3)), offset: 0 },
};

export const MACROS = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
};

const title = (text) => text.charAt(0).toUpperCase() + text.slice(1);

function toNumber(token, spec, fieldName) {
    const lower = token.toLowerCase();
    if (spec.names) {
        const index = spec.names.indexOf(lower);
        if (index >= 0) {
            return index + spec.offset;
        }
    }
    if (!/^\d+$/.test(token)) {
        throw new Error(`"${token}" is not valid in the ${fieldName} field.`);
    }
    const value = Number(token);
    if (value < spec.min || value > spec.max) {
        throw new Error(`${value} is out of range for the ${fieldName} field (${spec.min}-${spec.max}).`);
    }
    return value;
}

function parseField(raw, fieldName) {
    const spec = FIELDS[fieldName];
    if (/[LW#]/i.test(raw) && !(spec.names && spec.names.some((n) => raw.toLowerCase().includes(n)))) {
        throw new Error(`"${raw}" uses Quartz-only syntax (L, W or #), which standard cron does not support.`);
    }
    const values = new Set();
    for (const part of raw.split(",")) {
        if (!part) {
            throw new Error(`Empty list item in the ${fieldName} field.`);
        }
        const [range, stepText] = part.split("/");
        let step = 1;
        if (stepText !== undefined) {
            if (!/^\d+$/.test(stepText) || Number(stepText) === 0) {
                throw new Error(`Step "/${stepText}" must be a positive number.`);
            }
            step = Number(stepText);
        }
        let start;
        let end;
        if (range === "*" || range === "?") {
            start = spec.min;
            end = fieldName === "dow" ? 6 : spec.max;
        } else if (range.includes("-")) {
            const [a, b] = range.split("-");
            start = toNumber(a, spec, fieldName);
            end = toNumber(b, spec, fieldName);
            if (end < start) {
                throw new Error(`Range ${range} in the ${fieldName} field runs backwards.`);
            }
        } else {
            start = toNumber(range, spec, fieldName);
            end = stepText !== undefined ? (fieldName === "dow" ? 6 : spec.max) : start;
        }
        for (let v = start; v <= end; v += step) {
            values.add(fieldName === "dow" && v === 7 ? 0 : v);
        }
    }
    return { raw, values, star: raw.startsWith("*") || raw.startsWith("?") };
}

export function parseCron(expression) {
    let text = String(expression).trim().replace(/\s+/g, " ");
    if (!text) {
        throw new Error("Enter a cron expression.");
    }
    const macro = MACROS[text.toLowerCase()];
    if (macro) {
        text = macro;
    } else if (text.startsWith("@")) {
        throw new Error(`Unknown macro ${text}. Supported: ${Object.keys(MACROS).join(", ")}.`);
    }
    const parts = text.split(" ");
    if (parts.length !== 5 && parts.length !== 6) {
        throw new Error(`Expected 5 fields (minute hour day month weekday) or 6 with seconds first; got ${parts.length}.`);
    }
    const hasSeconds = parts.length === 6;
    const names = hasSeconds
        ? ["second", "minute", "hour", "dom", "month", "dow"]
        : ["minute", "hour", "dom", "month", "dow"];
    const schedule = { expression: text, hasSeconds };
    names.forEach((name, i) => {
        schedule[name] = parseField(parts[i], name);
    });
    if (!hasSeconds) {
        schedule.second = { raw: "0", values: new Set([0]), star: false };
    }
    return schedule;
}

function joinList(items) {
    if (items.length <= 1) return items.join("");
    return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

const pad = (n) => String(n).padStart(2, "0");

function formatValue(fieldName, value) {
    if (fieldName === "month") return title(MONTHS[value - 1]);
    if (fieldName === "dow") return title(DAYS[value % 7]);
    if (fieldName === "hour") return `${pad(value)}:00`;
    return String(value);
}

function isSingle(field) {
    return /^\d+$/.test(field.raw);
}

function numericList(field) {
    return field.raw.split(",").every((p) => /^\d+$/.test(p)) ? field.raw.split(",").map(Number) : null;
}

/** Describe one field from its raw tokens, e.g. "every 15 minutes" or "Monday through Friday". */
function describeParts(field, fieldName) {
    const spec = FIELDS[fieldName];
    const valueOf = (token) => toNumber(token, spec, fieldName);
    const plural = spec.unit === "day of the week" ? "days of the week" : `${spec.unit}s`;
    return joinList(
        field.raw.split(",").map((part) => {
            const [range, step] = part.split("/");
            const every = step
                ? Number(step) === 1 ? `every ${spec.unit}` : `every ${step} ${plural}`
                : "";
            if (range === "*" || range === "?") {
                return step ? every : `every ${spec.unit}`;
            }
            if (range.includes("-")) {
                const [a, b] = range.split("-").map(valueOf);
                const span = `${formatValue(fieldName, a)} through ${formatValue(fieldName, b)}`;
                return step ? `${every} from ${span}` : span;
            }
            const value = formatValue(fieldName, valueOf(range));
            return step ? `${every} starting at ${value}` : value;
        })
    );
}

function describeTime(s) {
    const minutes = numericList(s.minute);
    const hours = numericList(s.hour);
    const seconds = s.hasSeconds ? numericList(s.second) : [0];
    const secondSuffix = (sec) => (s.hasSeconds ? `:${pad(sec)}` : "");
    if (minutes && hours && seconds && minutes.length * hours.length * seconds.length <= 8) {
        const times = [];
        for (const h of hours) {
            for (const m of minutes) {
                for (const sec of seconds) {
                    times.push(`${pad(h)}:${pad(m)}${secondSuffix(sec)}`);
                }
            }
        }
        return `At ${joinList(times)}`;
    }
    let text;
    if (s.minute.raw === "*") {
        text = "Every minute";
    } else if (isSingle(s.minute)) {
        text = `At minute ${s.minute.raw}`;
    } else if (/^\*\/\d+$/.test(s.minute.raw)) {
        text = title(describeParts(s.minute, "minute"));
    } else {
        text = `At minutes ${describeParts(s.minute, "minute")}`;
    }
    if (s.hasSeconds && s.second.raw !== "0") {
        const secondText = s.second.raw === "*"
            ? "every second"
            : /^\*\//.test(s.second.raw)
              ? describeParts(s.second, "second")
              : `at second ${describeParts(s.second, "second")}`;
        text = s.minute.raw === "*"
            ? title(secondText)
            : `${title(secondText)}, ${text.charAt(0).toLowerCase()}${text.slice(1)}`;
    }
    if (s.hour.raw === "*") {
        return s.minute.raw === "*" || /^\*\//.test(s.minute.raw) ? text : `${text} past every hour`;
    }
    if (hours) {
        return `${text} past hour ${joinList(hours.map(String))}`;
    }
    const range = s.hour.raw.match(/^(\d+)-(\d+)$/);
    if (range) {
        return `${text}, between ${pad(Number(range[1]))}:00 and ${pad(Number(range[2]))}:59`;
    }
    return `${text}, ${describeParts(s.hour, "hour")}`;
}

export function describeCron(schedule) {
    const pieces = [describeTime(schedule)];
    const domText = schedule.dom.star
        ? ""
        : isSingle(schedule.dom)
          ? `on day ${schedule.dom.raw} of the month`
          : /^\*\//.test(schedule.dom.raw)
            ? describeParts(schedule.dom, "dom")
            : `on days ${describeParts(schedule.dom, "dom")} of the month`;
    const dowText = schedule.dow.star && schedule.dow.raw === "*" ? "" : `on ${describeParts(schedule.dow, "dow")}`;
    if (domText && dowText && !schedule.dow.star) {
        pieces.push(`${domText} or ${dowText}`);
    } else {
        if (domText) pieces.push(domText);
        if (dowText) pieces.push(dowText);
    }
    if (schedule.month.raw !== "*") {
        const monthText = describeParts(schedule.month, "month");
        pieces.push(/^every/.test(monthText) ? monthText : `in ${monthText}`);
    }
    return `${pieces.join(", ")}.`;
}

const LOCAL = {
    year: "getFullYear", month: "getMonth", date: "getDate", day: "getDay",
    hours: "getHours", minutes: "getMinutes", seconds: "getSeconds",
    setDate: "setDate", setMonth: "setMonth", setHours: "setHours", setMinutes: "setMinutes", setSeconds: "setSeconds",
};
const UTC = {
    year: "getUTCFullYear", month: "getUTCMonth", date: "getUTCDate", day: "getUTCDay",
    hours: "getUTCHours", minutes: "getUTCMinutes", seconds: "getUTCSeconds",
    setDate: "setUTCDate", setMonth: "setUTCMonth", setHours: "setUTCHours", setMinutes: "setUTCMinutes", setSeconds: "setUTCSeconds",
};

function dayMatches(schedule, d, api) {
    const domOk = schedule.dom.values.has(d[api.date]());
    const dowOk = schedule.dow.values.has(d[api.day]());
    if (schedule.dom.star && schedule.dow.star) return true;
    if (schedule.dom.star) return dowOk;
    if (schedule.dow.star) return domOk;
    // Vixie cron: when both day fields are restricted, either may match.
    return domOk || dowOk;
}

export function nextRuns(schedule, from = new Date(), count = 5, { utc = false } = {}) {
    const api = utc ? UTC : LOCAL;
    const d = new Date(from.getTime());
    d.setMilliseconds(0);
    d[api.setSeconds](d[api.seconds]() + 1);
    const limitYear = d[api.year]() + 12;
    const runs = [];
    let guard = 0;
    while (runs.length < count && guard < 500000 && d[api.year]() <= limitYear) {
        guard += 1;
        if (!schedule.month.values.has(d[api.month]() + 1)) {
            d[api.setMonth](d[api.month]() + 1, 1);
            d[api.setHours](0, 0, 0);
            continue;
        }
        if (!dayMatches(schedule, d, api)) {
            d[api.setDate](d[api.date]() + 1);
            d[api.setHours](0, 0, 0);
            continue;
        }
        if (!schedule.hour.values.has(d[api.hours]())) {
            d[api.setHours](d[api.hours]() + 1, 0, 0);
            continue;
        }
        if (!schedule.minute.values.has(d[api.minutes]())) {
            d[api.setMinutes](d[api.minutes]() + 1, 0);
            continue;
        }
        if (!schedule.second.values.has(d[api.seconds]())) {
            d[api.setSeconds](d[api.seconds]() + 1);
            continue;
        }
        runs.push(new Date(d.getTime()));
        d[api.setSeconds](d[api.seconds]() + 1);
    }
    return runs;
}

export const EXAMPLES = [
    ["*/5 * * * *", "Every 5 minutes"],
    ["0 * * * *", "Hourly"],
    ["0 9 * * 1-5", "Weekdays at 09:00"],
    ["30 2 * * 0", "Sundays at 02:30"],
    ["0 0 1 * *", "Monthly"],
    ["0 0 1 1 *", "Yearly"],
    ["0 8-18/2 * * *", "Every 2 hours, 08:00-18:00"],
];

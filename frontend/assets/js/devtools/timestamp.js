const UNITS = [
    { unit: "seconds", limit: 1e11, toMs: 1e3 },
    { unit: "milliseconds", limit: 1e14, toMs: 1 },
    { unit: "microseconds", limit: 1e17, toMs: 1e-3 },
    { unit: "nanoseconds", limit: Infinity, toMs: 1e-6 },
];

const MAX_DATE_MS = 8.64e15;

/**
 * Interpret a bare number as a Unix timestamp. The unit is inferred from
 * magnitude: anything below 1e11 is seconds (covers years 1970-5138), then
 * milliseconds, microseconds and nanoseconds.
 */
export function detectTimestamp(value, forcedUnit = "auto") {
    const number = Number(value);
    if (!Number.isFinite(number)) {
        return null;
    }
    const abs = Math.abs(number);
    const entry =
        forcedUnit === "auto"
            ? UNITS.find((candidate) => abs < candidate.limit)
            : UNITS.find((candidate) => candidate.unit === forcedUnit);
    if (!entry) {
        return null;
    }
    const ms = Math.round(number * entry.toMs);
    if (Math.abs(ms) > MAX_DATE_MS) {
        return null;
    }
    return { ms, unit: entry.unit };
}

export function parseInput(text, forcedUnit = "auto") {
    const trimmed = String(text).trim();
    if (!trimmed) {
        throw new Error("Enter a Unix timestamp or a date.");
    }
    if (/^[-+]?\d+(\.\d+)?$/.test(trimmed)) {
        const detected = detectTimestamp(trimmed, forcedUnit);
        if (!detected) {
            throw new Error("That timestamp is outside the range JavaScript dates support.");
        }
        return { ...detected, source: "timestamp" };
    }
    const ms = Date.parse(trimmed);
    if (Number.isNaN(ms)) {
        throw new Error(
            "Could not read that as a date. Try ISO 8601 (2024-05-01T12:00:00Z) or a Unix timestamp."
        );
    }
    return { ms, unit: null, source: "date" };
}

function partsIn(ms, timeZone) {
    const formatter = new Intl.DateTimeFormat("en-US", {
        timeZone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hourCycle: "h23",
        era: "short",
    });
    const parts = {};
    for (const part of formatter.formatToParts(new Date(ms))) {
        parts[part.type] = part.value;
    }
    return parts;
}

export function offsetMinutes(ms, timeZone) {
    const p = partsIn(ms, timeZone);
    let year = Number(p.year);
    if (p.era && /^B/i.test(p.era)) {
        year = 1 - year;
    }
    const wall = new Date(Date.UTC(2000, Number(p.month) - 1, Number(p.day), Number(p.hour), Number(p.minute), Number(p.second)));
    // Date.UTC maps years 0-99 to 1900-1999, so set the real year separately.
    wall.setUTCFullYear(year, Number(p.month) - 1, Number(p.day));
    const asUtc = wall.getTime();
    const floored = ms - (((ms % 1000) + 1000) % 1000);
    return Math.round((asUtc - floored) / 60000);
}

function formatOffset(minutes) {
    const sign = minutes < 0 ? "-" : "+";
    const abs = Math.abs(minutes);
    return `${sign}${String(Math.floor(abs / 60)).padStart(2, "0")}:${String(abs % 60).padStart(2, "0")}`;
}

export function isoInZone(ms, timeZone) {
    const offset = offsetMinutes(ms, timeZone);
    const shifted = new Date(ms + offset * 60000).toISOString();
    return `${shifted.slice(0, -1)}${formatOffset(offset)}`;
}

export function humanInZone(ms, timeZone, locale = undefined) {
    return new Intl.DateTimeFormat(locale, {
        timeZone,
        dateStyle: "full",
        timeStyle: "long",
    }).format(new Date(ms));
}

const RELATIVE_STEPS = [
    ["year", 365.25 * 24 * 3600 * 1000],
    ["month", 30.44 * 24 * 3600 * 1000],
    ["week", 7 * 24 * 3600 * 1000],
    ["day", 24 * 3600 * 1000],
    ["hour", 3600 * 1000],
    ["minute", 60 * 1000],
    ["second", 1000],
];

export function relativeTime(ms, now = Date.now(), locale = "en") {
    const diff = ms - now;
    const formatter = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
    for (const [unit, size] of RELATIVE_STEPS) {
        if (Math.abs(diff) >= size || unit === "second") {
            return formatter.format(Math.round(diff / size), unit);
        }
    }
    return "";
}

export function dayOfYear(ms, timeZone) {
    const p = partsIn(ms, timeZone);
    const year = Number(p.year);
    const start = Date.UTC(year, 0, 1);
    const current = Date.UTC(year, Number(p.month) - 1, Number(p.day));
    return Math.round((current - start) / 86400000) + 1;
}

export function isoWeek(ms, timeZone) {
    const p = partsIn(ms, timeZone);
    const date = new Date(Date.UTC(Number(p.year), Number(p.month) - 1, Number(p.day)));
    const weekday = date.getUTCDay() || 7;
    date.setUTCDate(date.getUTCDate() + 4 - weekday);
    const yearStart = Date.UTC(date.getUTCFullYear(), 0, 1);
    return {
        year: date.getUTCFullYear(),
        week: Math.ceil(((date.getTime() - yearStart) / 86400000 + 1) / 7),
    };
}

export function conversions(ms, timeZone, now = Date.now()) {
    const week = isoWeek(ms, timeZone);
    return [
        ["Unix seconds", String(Math.floor(ms / 1000))],
        ["Unix milliseconds", String(ms)],
        ["ISO 8601 (UTC)", new Date(ms).toISOString()],
        [`ISO 8601 (${timeZone})`, isoInZone(ms, timeZone)],
        ["RFC 7231 / HTTP date", new Date(ms).toUTCString()],
        [`Readable (${timeZone})`, humanInZone(ms, timeZone)],
        ["Relative", relativeTime(ms, now)],
        ["Day of year / ISO week", `Day ${dayOfYear(ms, timeZone)} · Week ${week.week} of ${week.year}`],
    ];
}

export function listTimeZones() {
    let zones = [];
    try {
        zones = Intl.supportedValuesOf("timeZone");
    } catch {
        zones = [];
    }
    if (!zones.length) {
        zones = [
            "America/Los_Angeles", "America/Denver", "America/Chicago", "America/New_York",
            "America/Sao_Paulo", "Europe/London", "Europe/Berlin", "Europe/Moscow", "Africa/Lagos",
            "Africa/Johannesburg", "Asia/Dubai", "Asia/Kolkata", "Asia/Shanghai", "Asia/Tokyo",
            "Australia/Sydney", "Pacific/Auckland",
        ];
    }
    return ["UTC", ...zones.filter((zone) => zone !== "UTC")];
}

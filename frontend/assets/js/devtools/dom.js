let liveRegion = null;

export function announce(message) {
    if (!liveRegion) {
        liveRegion = document.createElement("div");
        liveRegion.className = "visually-hidden";
        liveRegion.setAttribute("aria-live", "polite");
        liveRegion.setAttribute("role", "status");
        document.body.appendChild(liveRegion);
    }
    liveRegion.textContent = "";
    // A fresh text node after clearing makes screen readers repeat identical messages.
    setTimeout(() => {
        liveRegion.textContent = message;
    }, 30);
}

export async function copyText(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch {
        const area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        let ok = false;
        try {
            ok = document.execCommand("copy");
        } catch {
            ok = false;
        }
        area.remove();
        return ok;
    }
}

export function wireCopy(button, getText, { emptyMessage = "Nothing to copy yet." } = {}) {
    const original = button.textContent;
    let timer = null;
    button.addEventListener("click", async () => {
        const text = getText();
        if (!text) {
            announce(emptyMessage);
            return;
        }
        const ok = await copyText(text);
        button.textContent = ok ? "Copied" : "Copy failed";
        announce(ok ? "Copied to clipboard." : "Copy failed. Select the text and copy it manually.");
        clearTimeout(timer);
        timer = setTimeout(() => {
            button.textContent = original;
        }, 1500);
    });
    return button;
}

export function copyButton(getText, label = "Copy", accessibleName = "") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary-button";
    button.textContent = label;
    if (accessibleName) {
        button.setAttribute("aria-label", accessibleName);
    }
    return wireCopy(button, getText);
}

export function debounce(fn, wait = 150) {
    let timer = null;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), wait);
    };
}

export function el(tag, props = {}, children = []) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
        if (value === undefined || value === null || value === false) {
            continue;
        }
        if (key === "text") {
            node.textContent = value;
        } else if (key === "className") {
            node.className = value;
        } else {
            node.setAttribute(key, value === true ? "" : String(value));
        }
    }
    for (const child of [].concat(children)) {
        if (child === null || child === undefined || child === false) {
            continue;
        }
        node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    }
    return node;
}

export function clear(node) {
    while (node.firstChild) {
        node.removeChild(node.firstChild);
    }
}

export function wireSegmented(group, onChange) {
    const buttons = Array.from(group.querySelectorAll("button[data-value]"));
    const select = (value) => {
        for (const button of buttons) {
            const active = button.dataset.value === value;
            button.classList.toggle("active", active);
            button.setAttribute("aria-pressed", String(active));
        }
    };
    for (const button of buttons) {
        button.addEventListener("click", () => {
            select(button.dataset.value);
            onChange(button.dataset.value);
        });
    }
    const initial = buttons.find((button) => button.classList.contains("active")) || buttons[0];
    if (initial) {
        select(initial.dataset.value);
    }
    return {
        get value() {
            const active = buttons.find((button) => button.classList.contains("active"));
            return active ? active.dataset.value : null;
        },
        set: select,
    };
}

export function keyValueTable(rows, { caption = "", copyLabel = "Copy" } = {}) {
    const table = el("table", { className: "analysis-table" });
    if (caption) {
        table.appendChild(el("caption", { className: "visually-hidden", text: caption }));
    }
    const body = el("tbody");
    for (const [label, value] of rows) {
        const valueText = value === null || value === undefined ? "" : String(value);
        body.appendChild(
            el("tr", {}, [
                el("th", { scope: "row", text: label }),
                el("td", {}, [el("code", { text: valueText })]),
                el("td", {}, [copyButton(() => valueText, copyLabel, `${copyLabel} ${label}`)]),
            ])
        );
    }
    table.appendChild(body);
    return table;
}

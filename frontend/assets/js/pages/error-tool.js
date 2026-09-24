import "./error-page.js";

const params = new URLSearchParams(window.location.search);
const tool = params.get("tool");
const code = params.get("code");

if (tool) {
    const chip = document.querySelector("#tool-error-status");
    const title = document.querySelector("#tool-error-title");
    const lead = document.querySelector("#tool-error-lead");
    const back = document.querySelector("#tool-error-back");
    const display = document.querySelector("#tool-error-code");

    if (chip) {
        chip.textContent = `status: tool_error · ${tool}`;
    }
    if (display) {
        display.textContent = "!";
    }
    if (title) {
        title.textContent = "This tool hit a problem.";
    }
    if (lead) {
        lead.textContent =
            `The ${tool.replace(/-/g, " ")} tool could not finish the job. ` +
            "Go back and try again, or check the file before retrying.";
    }
    if (back && back.href) {
        back.href = `/tools/${encodeURIComponent(tool)}`;
    }
    if (code) {
        const detail = document.querySelector("#error-detail");
        if (detail) {
            detail.textContent = code;
            detail.hidden = false;
        }
    }
    document.title = "Tool error - Utils-tool";
}

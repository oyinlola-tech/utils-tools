import { initToolPage, setupUpload } from "./tool-kit.js";
import { apiUpload } from "../api.js";
import { formatBytes } from "../utils.js";

const kit = await initToolPage("file-analyzer");
if (!kit.available) {
    setupUpload({ onFiles: () => {} });
} else {
    let files = [];
    setupUpload({
        onFiles: (selected) => {
            files = selected;
        },
    });

    document.querySelector("#tool-run").addEventListener("click", async () => {
        if (!files.length) {
            kit.banner.show("Choose files to analyze.");
            return;
        }
        kit.banner.hide();
        kit.setBusy(true, "Analyzing files...");
        try {
            const data = await apiUpload("/tools/file/analyze", {
                files: files.map((file) => ({ name: "files", file })),
            });
            kit.setBusy(false);
            const host = document.querySelector("#tool-results");
            host.innerHTML = "";
            const table = document.createElement("table");
            table.className = "analysis-table";
            table.innerHTML = `
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Size</th>
                    <th>Dimensions</th>
                    <th>Pages</th>
                    <th>SHA-256</th>
                  </tr>
                </thead>`;
            const body = document.createElement("tbody");
            for (const item of data.files) {
                const row = document.createElement("tr");
                const dims = item.width ? `${item.width}×${item.height}px` : "—";
                const pages = item.page_count != null ? item.page_count : "—";
                // Build cells with textContent: filenames are user-controlled
                // and must never be parsed as HTML.
                const cells = [
                    item.filename,
                    `${item.category} (${item.mime_type})`,
                    formatBytes(item.size_bytes),
                    dims,
                    String(pages),
                ];
                for (const text of cells) {
                    const cell = document.createElement("td");
                    cell.textContent = text;
                    row.appendChild(cell);
                }
                const hashCell = document.createElement("td");
                const code = document.createElement("code");
                code.title = item.sha256;
                code.textContent = `${item.sha256.slice(0, 16)}…`;
                hashCell.appendChild(code);
                row.appendChild(hashCell);
                body.appendChild(row);
            }
            table.appendChild(body);
            host.appendChild(table);
            kit.showResult();
        } catch (error) {
            kit.setBusy(false);
            kit.banner.show(error.message);
        }
    });
}

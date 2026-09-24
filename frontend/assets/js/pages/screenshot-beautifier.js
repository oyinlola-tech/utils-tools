import { initToolPage, setupUpload, triggerDownload } from "./tool-kit.js";

const kit = await initToolPage("screenshot-beautifier");
if (!kit.available) {
    setupUpload({ onFiles: () => {} });
} else {
    let source = null;
    let sourceUrl = null;
    let sourceName = "screenshot";

    const frame = document.querySelector("#shot-canvas-frame");
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    frame.appendChild(canvas);

    function roundedRectPath(context, x, y, w, h, r) {
        context.beginPath();
        context.moveTo(x + r, y);
        context.lineTo(x + w - r, y);
        context.arcTo(x + w, y, x + w, y + r, r);
        context.lineTo(x + w, y + h - r);
        context.arcTo(x + w, y + h, x + w - r, y + h, r);
        context.lineTo(x + r, y + h);
        context.arcTo(x, y + h, x, y + h - r, r);
        context.lineTo(x, y + r);
        context.arcTo(x, y, x + r, y, r);
        context.closePath();
    }

    function draw() {
        if (!source) {
            return;
        }
        const padding = Number(document.querySelector("#shot-padding").value);
        const radius = Number(document.querySelector("#shot-radius").value);
        const color = document.querySelector("#shot-color").value;
        const shadow = document.querySelector("#shot-shadow").value === "true";
        const scale = Math.min(900 / source.width, 900 / source.height, 1);
        const imgW = Math.round(source.width * scale);
        const imgH = Math.round(source.height * scale);
        const pad = Math.round(padding * scale * 2);
        canvas.width = imgW + pad;
        canvas.height = imgH + pad;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = color;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        const x = pad / 2;
        const y = pad / 2;
        ctx.save();
        roundedRectPath(ctx, x, y, imgW, imgH, radius);
        if (shadow) {
            ctx.shadowColor = "rgba(0, 0, 0, 0.35)";
            ctx.shadowBlur = 24 * scale;
            ctx.shadowOffsetY = 8 * scale;
        }
        ctx.fillStyle = "#ffffff";
        ctx.fill();
        ctx.restore();
        ctx.save();
        roundedRectPath(ctx, x, y, imgW, imgH, radius);
        ctx.clip();
        ctx.drawImage(source, x, y, imgW, imgH);
        ctx.restore();
    }

    for (const input of document.querySelectorAll(
        "#shot-padding, #shot-radius"
    )) {
        input.addEventListener("input", () => {
            const label = input.id === "shot-padding" ? "shot-padding-value" : "shot-radius-value";
            document.querySelector(`#${label}`).textContent = input.value;
            draw();
        });
    }
    document.querySelector("#shot-color").addEventListener("input", draw);
    document.querySelector("#shot-shadow").addEventListener("change", draw);

    setupUpload({
        onFiles: (files) => {
            const file = files[0];
            if (sourceUrl) {
                URL.revokeObjectURL(sourceUrl);
            }
            sourceUrl = URL.createObjectURL(file);
            sourceName = file.name || "screenshot";
            const image = new Image();
            image.onload = () => {
                kit.banner.hide();
                source = image;
                draw();
            };
            image.onerror = () => {
                kit.banner.show("This browser cannot open that image. Try a JPG, PNG or WebP file.");
            };
            image.src = sourceUrl;
        },
    });

    document.querySelector("#tool-run").addEventListener("click", () => {
        if (!source) {
            kit.banner.show("Choose a screenshot first.");
            return;
        }
        kit.banner.hide();
        const padding = Number(document.querySelector("#shot-padding").value);
        const radius = Number(document.querySelector("#shot-radius").value);
        const color = document.querySelector("#shot-color").value;
        const shadow = document.querySelector("#shot-shadow").value === "true";
        const imgW = source.width;
        const imgH = source.height;
        const pad = padding * 2;
        const outCanvas = document.createElement("canvas");
        const outCtx = outCanvas.getContext("2d");
        outCanvas.width = imgW + pad;
        outCanvas.height = imgH + pad;
        outCtx.fillStyle = color;
        outCtx.fillRect(0, 0, outCanvas.width, outCanvas.height);
        outCtx.save();
        roundedRectPath(outCtx, padding, padding, imgW, imgH, radius);
        if (shadow) {
            outCtx.shadowColor = "rgba(0, 0, 0, 0.35)";
            outCtx.shadowBlur = 40;
            outCtx.shadowOffsetY = 12;
        }
        outCtx.fillStyle = "#ffffff";
        outCtx.fill();
        outCtx.restore();
        outCtx.save();
        roundedRectPath(outCtx, padding, padding, imgW, imgH, radius);
        outCtx.clip();
        outCtx.drawImage(source, padding, padding);
        outCtx.restore();
        outCanvas.toBlob((blob) => {
            if (!blob) {
                kit.banner.show("The image is too large to export in this browser.");
                return;
            }
            // source.src is a blob: URL, so use the uploaded file's name.
            const name = `${sourceName.replace(/\.[^.]+$/, "")}-framed.png`;
            triggerDownload(blob, name);
        }, "image/png");
    });
}

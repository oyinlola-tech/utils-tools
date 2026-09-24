import { initToolPage, setupUpload, triggerDownload } from "./tool-kit.js";

const kit = await initToolPage("image-editor");
if (!kit.available) {
    setupUpload({ onFiles: () => {} });
} else {
    let source = null;
    let sourceUrl = null;
    let sourceName = "image";

    const frame = document.querySelector("#editor-canvas-frame");
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    frame.appendChild(canvas);

    const sliders = {
        brightness: document.querySelector("#brightness"),
        contrast: document.querySelector("#contrast"),
        saturation: document.querySelector("#saturation"),
        sharpness: document.querySelector("#sharpness"),
    };
    const labels = {
        brightness: document.querySelector("#brightness-value"),
        contrast: document.querySelector("#contrast-value"),
        saturation: document.querySelector("#saturation-value"),
        sharpness: document.querySelector("#sharpness-value"),
    };

    function filterString() {
        const b = Number(sliders.brightness.value);
        const c = Number(sliders.contrast.value);
        const s = Number(sliders.saturation.value);
        return `brightness(${1 + b / 100}) contrast(${1 + c / 100}) saturate(${1 + s / 100})`;
    }

    function draw() {
        if (!source) {
            return;
        }
        const scale = Math.min(900 / source.width, 900 / source.height, 1);
        canvas.width = Math.round(source.width * scale);
        canvas.height = Math.round(source.height * scale);
        ctx.filter = filterString();
        ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
        ctx.filter = "none";
    }

    for (const [key, input] of Object.entries(sliders)) {
        input.addEventListener("input", () => {
            labels[key].textContent = input.value;
            if (key !== "sharpness") {
                draw();
            }
        });
    }

    document.querySelector("#editor-reset").addEventListener("click", () => {
        for (const [key, input] of Object.entries(sliders)) {
            input.value = 0;
            labels[key].textContent = "0";
        }
        draw();
    });

    setupUpload({
        onFiles: (files) => {
            const file = files[0];
            if (sourceUrl) {
                URL.revokeObjectURL(sourceUrl);
            }
            sourceUrl = URL.createObjectURL(file);
            sourceName = file.name || "image";
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

    function applySharpness(image) {
        const value = Number(sliders.sharpness.value);
        if (value === 0) {
            return image;
        }
        const amount = value / 100;
        const kernel = [0, -amount, 0, -amount, 1 + 4 * amount, -amount, 0, -amount, 0];
        const sourceCtx = document.createElement("canvas").getContext("2d");
        sourceCtx.canvas.width = image.width;
        sourceCtx.canvas.height = image.height;
        sourceCtx.drawImage(image, 0, 0);
        const src = sourceCtx.getImageData(0, 0, image.width, image.height);
        const out = new ImageData(image.width, image.height);
        const size = 3;
        for (let y = 0; y < image.height; y++) {
            for (let x = 0; x < image.width; x++) {
                for (let channel = 0; channel < 3; channel++) {
                    let sum = 0;
                    for (let ky = 0; ky < size; ky++) {
                        for (let kx = 0; kx < size; kx++) {
                            const px = Math.min(image.width - 1, Math.max(0, x + kx - 1));
                            const py = Math.min(image.height - 1, Math.max(0, y + ky - 1));
                            sum +=
                                src.data[(py * image.width + px) * 4 + channel] *
                                kernel[ky * size + kx];
                        }
                    }
                    out.data[(y * image.width + x) * 4 + channel] = Math.max(
                        0,
                        Math.min(255, sum)
                    );
                }
                out.data[(y * image.width + x) * 4 + 3] =
                    src.data[(y * image.width + x) * 4 + 3];
            }
        }
        const canvas = document.createElement("canvas");
        canvas.width = image.width;
        canvas.height = image.height;
        const cctx = canvas.getContext("2d");
        cctx.putImageData(out, 0, 0);
        return canvas;
    }

    document.querySelector("#tool-run").addEventListener("click", () => {
        if (!source) {
            kit.banner.show("Choose an image first.");
            return;
        }
        kit.banner.hide();
        kit.setBusy(true, "Exporting edited image...");
        setTimeout(() => {
            const outCanvas = document.createElement("canvas");
            outCanvas.width = source.width;
            outCanvas.height = source.height;
            const outCtx = outCanvas.getContext("2d");
            outCtx.filter = filterString();
            outCtx.drawImage(source, 0, 0);
            outCtx.filter = "none";
            const final = applySharpness(outCanvas);
            final.toBlob((blob) => {
                kit.setBusy(false);
                if (!blob) {
                    kit.banner.show("The image is too large to export in this browser.");
                    return;
                }
                // source.src is a blob: URL, so it cannot supply the name.
                const name = `${sourceName.replace(/\.[^.]+$/, "")}-edited.png`;
                triggerDownload(blob, name);
            }, "image/png");
        }, 30);
    });
}

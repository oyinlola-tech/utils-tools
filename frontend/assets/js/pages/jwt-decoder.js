import { initToolPage } from "./tool-kit.js";
import { apiJsonPost, isInputError } from "../api.js";

const kit = await initToolPage("jwt-decoder");

const jwtInput = document.querySelector("#jwt-input");
const decodeBtn = document.querySelector("#tool-run");
const jwtOutput = document.querySelector("#jwt-output");
const headerPre = document.querySelector("#jwt-header-json");
const payloadPre = document.querySelector("#jwt-payload-json");

decodeBtn.addEventListener("click", async () => {
    const token = jwtInput.value.trim();
    if (!token) {
        kit.banner.show("Paste a JWT token first.");
        return;
    }

    kit.banner.hide();
    kit.setBusy(true, "Decoding JWT...");

    try {
        const res = await apiJsonPost("/tools/dev/jwt-decode", { token });
        kit.setBusy(false);

        if (res && res.data) {
            headerPre.textContent = JSON.stringify(res.data.header, null, 2);
            payloadPre.textContent = JSON.stringify(res.data.payload, null, 2);
            jwtOutput.classList.remove("hidden");
        }
    } catch (err) {
        kit.setBusy(false);
        jwtOutput.classList.add("hidden");
        if (isInputError(err)) {
            kit.banner.show(err.message);
        } else {
            kit.showError(err);
        }
    }
});

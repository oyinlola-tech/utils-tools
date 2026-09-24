import { initToolPage } from "./tool-kit.js";
import {
    generatePassword,
    generatePassphrase,
    passwordEntropy,
    passphraseEntropy,
    strength,
    crackTime,
} from "../devtools/password.js";
import { WORDS } from "../devtools/wordlist.js";
import { wireCopy, wireSegmented, debounce } from "../devtools/dom.js";

const kit = await initToolPage("password-generator");

if (kit.available) {
    const $ = (selector) => document.querySelector(selector);
    const passwordOptions = $("#pw-password-options");
    const phraseOptions = $("#pw-phrase-options");
    const length = $("#pw-length");
    const lengthRange = $("#pw-length-range");
    const count = $("#pw-count");
    const output = $("#pw-output");
    const meter = $("#pw-meter");
    const strengthText = $("#pw-strength");

    let mode = "password";

    const clampNumber = (input, min, max, fallback) => {
        const value = Math.floor(Number(input.value));
        return Number.isFinite(value) ? Math.min(max, Math.max(min, value)) : fallback;
    };

    function passwordSettings() {
        return {
            length: clampNumber(length, 4, 128, 20),
            lower: $("#pw-lower").checked,
            upper: $("#pw-upper").checked,
            digits: $("#pw-digits").checked,
            symbols: $("#pw-symbols").checked,
            excludeAmbiguous: $("#pw-ambiguous").checked,
        };
    }

    function phraseSettings() {
        return {
            words: clampNumber($("#pw-words"), 3, 12, 5),
            separator: $("#pw-separator").value,
            capitalize: $("#pw-capitalize").checked,
            includeNumber: $("#pw-number").checked,
        };
    }

    function generate() {
        const total = clampNumber(count, 1, 50, 1);
        try {
            const results = [];
            let bits;
            if (mode === "password") {
                const settings = passwordSettings();
                for (let i = 0; i < total; i += 1) {
                    results.push(generatePassword(settings));
                }
                bits = passwordEntropy(settings);
            } else {
                const settings = phraseSettings();
                for (let i = 0; i < total; i += 1) {
                    results.push(generatePassphrase(settings, WORDS));
                }
                bits = passphraseEntropy(settings, WORDS.length);
            }
            output.value = results.join("\n");
            output.rows = Math.min(10, Math.max(3, total));
            const rating = strength(bits);
            meter.value = Math.min(128, bits);
            meter.textContent = rating.label;
            strengthText.textContent = `${rating.label} · about ${Math.round(bits)} bits of entropy · ${crackTime(bits)} to guess at 10 billion guesses per second.`;
            kit.banner.hide();
        } catch (error) {
            output.value = "";
            meter.value = 0;
            strengthText.textContent = "";
            kit.banner.show(error.message);
        }
    }

    wireSegmented($("#pw-mode"), (value) => {
        mode = value;
        passwordOptions.classList.toggle("hidden", value !== "password");
        phraseOptions.classList.toggle("hidden", value !== "passphrase");
        generate();
    });

    length.addEventListener("input", () => {
        lengthRange.value = String(clampNumber(length, 4, 128, 20));
    });
    length.addEventListener("input", debounce(generate, 200));
    lengthRange.addEventListener("input", () => {
        length.value = lengthRange.value;
        generate();
    });
    lengthRange.setAttribute("aria-valuetext", `${lengthRange.value} characters`);
    lengthRange.addEventListener("input", () => {
        lengthRange.setAttribute("aria-valuetext", `${lengthRange.value} characters`);
    });
    for (const selector of ["#pw-words", "#pw-count"]) {
        $(selector).addEventListener("input", debounce(generate, 200));
    }
    for (const selector of ["#pw-lower", "#pw-upper", "#pw-digits", "#pw-symbols", "#pw-ambiguous", "#pw-capitalize", "#pw-number", "#pw-separator"]) {
        $(selector).addEventListener("change", generate);
    }
    $("#pw-generate").addEventListener("click", generate);
    wireCopy($("#pw-copy"), () => output.value);

    generate();
}

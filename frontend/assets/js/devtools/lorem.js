export const WORDS = [...new Set((
    "lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et " +
    "dolore magna aliqua enim ad minim veniam quis nostrud exercitation ullamco laboris nisi aliquip ex ea " +
    "commodo consequat duis aute irure in reprehenderit voluptate velit esse cillum fugiat nulla pariatur " +
    "excepteur sint occaecat cupidatat non proident sunt culpa qui officia deserunt mollit anim id est " +
    "laborum curabitur pretium tincidunt lacus nunc pulvinar sapien ligula ornare ac augue vel vestibulum " +
    "morbi blandit cursus risus at ultrices mi quam lectus vitae aliquet nec ullamcorper eget nulla facilisi " +
    "etiam dignissim diam donec massa sapien faucibus viverra accumsan felis bibendum arcu feugiat pretium " +
    "nibh ipsum egestas integer quis auctor sollicitudin tellus gravida hendrerit vivamus porta lacinia " +
    "mattis maecenas volutpat suscipit tristique senectus netus malesuada fames turpis condimentum mauris " +
    "sagittis orci phasellus scelerisque fermentum odio pellentesque habitant semper posuere urna dictum " +
    "varius duis convallis tortor quam aenean euismod elementum nisl purus neque imperdiet proin libero"
).split(" "))];

const OPENING = "Lorem ipsum dolor sit amet, consectetur adipiscing elit";

/** Small deterministic PRNG (mulberry32) so tests can seed output. */
export function seededRandom(seed) {
    let state = seed >>> 0;
    return () => {
        state = (state + 0x6d2b79f5) >>> 0;
        let t = state;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

const between = (random, min, max) => min + Math.floor(random() * (max - min + 1));
const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1);

function words(count, random) {
    const out = [];
    for (let i = 0; i < count; i += 1) {
        let word = WORDS[Math.floor(random() * WORDS.length)];
        if (out.length && word === out[out.length - 1]) {
            word = WORDS[(WORDS.indexOf(word) + 1) % WORDS.length];
        }
        out.push(word);
    }
    return out;
}

function sentence(random) {
    const list = words(between(random, 6, 14), random);
    if (list.length > 7 && random() < 0.5) {
        const at = between(random, 2, list.length - 3);
        list[at] += ",";
    }
    return `${capitalize(list.join(" "))}.`;
}

function paragraph(random) {
    const count = between(random, 4, 7);
    const out = [];
    for (let i = 0; i < count; i += 1) {
        out.push(sentence(random));
    }
    return out.join(" ");
}

export function generateLorem({ unit = "paragraphs", count = 3, startWithLorem = true, html = false } = {}, random = Math.random) {
    const total = Math.max(1, Math.min(unit === "words" ? 5000 : 200, Math.floor(count) || 1));
    if (unit === "words") {
        const list = words(total, random);
        if (startWithLorem) {
            const opening = OPENING.replace(",", "").toLowerCase().split(" ");
            list.splice(0, Math.min(opening.length, total), ...opening.slice(0, total));
        }
        const text = capitalize(list.join(" "));
        return html ? `<p>${text}</p>` : text;
    }
    const make = unit === "sentences" ? sentence : paragraph;
    const blocks = [];
    for (let i = 0; i < total; i += 1) {
        blocks.push(make(random));
    }
    if (startWithLorem) {
        const first = blocks[0];
        const rest = first.slice(first.indexOf(".") + 1).trim();
        blocks[0] = unit === "sentences" ? `${OPENING}.` : `${OPENING}. ${rest}`.trim();
    }
    if (unit === "sentences") {
        return html ? `<p>${blocks.join(" ")}</p>` : blocks.join(" ");
    }
    return html ? blocks.map((block) => `<p>${block}</p>`).join("\n") : blocks.join("\n\n");
}

export function countStats(text) {
    const plain = text.replace(/<[^>]+>/g, "");
    return { words: (plain.match(/[A-Za-z]+/g) || []).length, characters: plain.length };
}

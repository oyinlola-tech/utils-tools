// Carries files from the home page drop target to the tool the user picks,
// so they don't have to choose the same file twice. IndexedDB can store
// File objects directly; nothing leaves the browser.

const DB_NAME = "utils-handoff";
const STORE = "files";
const KEY = "pending";
const MAX_AGE_MS = 10 * 60 * 1000;

function openDb() {
    return new Promise((resolve, reject) => {
        if (!("indexedDB" in window)) {
            reject(new Error("IndexedDB unavailable"));
            return;
        }
        const request = indexedDB.open(DB_NAME, 1);
        request.onupgradeneeded = () => request.result.createObjectStore(STORE);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

function run(mode, action) {
    return openDb().then(
        (db) =>
            new Promise((resolve, reject) => {
                const tx = db.transaction(STORE, mode);
                const result = action(tx.objectStore(STORE));
                tx.oncomplete = () => {
                    db.close();
                    resolve(result && "result" in result ? result.result : undefined);
                };
                tx.onerror = () => {
                    db.close();
                    reject(tx.error);
                };
            })
    );
}

export async function stashFiles(files) {
    try {
        await run("readwrite", (store) =>
            store.put({ files: Array.from(files), at: Date.now() }, KEY)
        );
        return true;
    } catch {
        return false;
    }
}

export async function takeFiles() {
    try {
        const entry = await run("readonly", (store) => store.get(KEY));
        if (!entry) {
            return [];
        }
        await run("readwrite", (store) => store.delete(KEY));
        if (Date.now() - entry.at > MAX_AGE_MS) {
            return [];
        }
        return entry.files || [];
    } catch {
        return [];
    }
}

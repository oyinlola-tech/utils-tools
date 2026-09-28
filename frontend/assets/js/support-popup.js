import { icon } from "./icons.js";

const STORAGE_KEY = "lr_usage_count";
const SHOWN_KEY = "lr_support_popup_shown";
const SUPPORT_URL =
  "https://myhappr.com/embed/oyinlola?color=%235EB5FF&title=Support+Oluwayemi+Oyinlola";
// Room the modal leaves around the form: its header and the page margin.
const HEADER_HEIGHT = "48px";

function supportFrame() {
  const frame = document.createElement("iframe");
  frame.src = SUPPORT_URL;
  frame.title = "Support Oluwayemi Oyinlola";
  frame.style.display = "block";
  frame.style.width = "100%";
  frame.style.border = "0";
  frame.style.borderRadius = "0 0 12px 12px";
  // As tall as the screen allows and free to scroll. At a fixed 600
  // pixels with scrolling off, the last step's button sat below the
  // fold on laptop screens and could not be reached.
  frame.style.height = `min(720px, calc(90vh - ${HEADER_HEIGHT}))`;
  // Where supported: the height that excludes a phone's browser bars.
  frame.style.height = `min(720px, calc(90dvh - ${HEADER_HEIGHT}))`;
  return frame;
}

function getCount() {
  try {
    return Number(localStorage.getItem(STORAGE_KEY) || 0);
  } catch (e) {
    return 0;
  }
}

function setCount(n) {
  try {
    localStorage.setItem(STORAGE_KEY, String(n));
  } catch (e) {
  }
}

function markShown() {
  try {
    localStorage.setItem(SHOWN_KEY, "1");
  } catch (e) {}
}

function alreadyShown() {
  try {
    return localStorage.getItem(SHOWN_KEY) === "1";
  } catch (e) {
    return false;
  }
}

function createModal(content) {
  const overlay = document.createElement("div");
  overlay.style.position = "fixed";
  overlay.style.inset = "0";
  overlay.style.background = "rgba(0,0,0,0.5)";
  overlay.style.display = "flex";
  overlay.style.alignItems = "center";
  overlay.style.justifyContent = "center";
  overlay.style.zIndex = "9999";

  const modal = document.createElement("div");
  modal.style.width = "min(900px, 95%)";
  modal.style.maxHeight = "90vh";
  modal.style.background = "#fff";
  modal.style.borderRadius = "12px";
  modal.style.overflow = "hidden";
  modal.style.boxShadow = "0 10px 30px rgba(0,0,0,0.3)";

  const header = document.createElement("div");
  header.style.display = "flex";
  header.style.justifyContent = "flex-end";
  header.style.alignItems = "center";
  header.style.boxSizing = "border-box";
  header.style.height = HEADER_HEIGHT;
  header.style.padding = "8px";

  const close = document.createElement("button");
  close.setAttribute("aria-label", "Close");
  close.style.border = "none";
  close.style.background = "transparent";
  close.style.fontSize = "20px";
  close.style.lineHeight = "1";
  close.style.padding = "4px";
  close.style.cursor = "pointer";
  close.appendChild(icon("xmark"));

  header.appendChild(close);

  const body = document.createElement("div");
  body.style.padding = "0";
  body.appendChild(content);

  modal.appendChild(header);
  modal.appendChild(body);
  overlay.appendChild(modal);

  // Scrolling belongs to the form while it is open, not the page behind.
  const root = document.documentElement;
  const pageOverflow = root.style.overflow;
  root.style.overflow = "hidden";

  function onKey(ev) {
    if (ev.key === "Escape") closeModal();
  }

  function closeModal() {
    root.style.overflow = pageOverflow;
    document.removeEventListener("keydown", onKey);
    try {
      document.body.removeChild(overlay);
    } catch (e) {}
  }

  document.addEventListener("keydown", onKey);
  close.addEventListener("click", () => {
    closeModal();
  });

  overlay.addEventListener("click", (ev) => {
    if (ev.target === overlay) closeModal();
  });

  return { overlay, closeModal };
}

export function openSupport() {
  const { overlay } = createModal(supportFrame());
  document.body.appendChild(overlay);
}

export function registerUse() {
  const count = getCount() + 1;
  setCount(count);

  if (count >= 3 && !alreadyShown()) {
    setTimeout(() => {
      openSupport();
      markShown();
    }, 200);
  }
}

export function resetUsage() {
  try {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(SHOWN_KEY);
  } catch (e) {}
}

export default { registerUse, resetUsage, openSupport };


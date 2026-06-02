// Lightweight Solve-panel ENTRY for editor mode — a floating launcher button that toggles a
// floating card holding the (already verified) editor solve panel. Deliberately NOT a dock
// system: the card is fixed-positioned, so it never reflows the editor canvas, and it lives
// entirely in the product layer (no CADGameFusion toolbar / submodule change).
//
// `buildSolveEntry` only builds the chrome + wires the open/close toggle and returns the inner
// region element for the caller to mount the real panel into; it has no solver/bridge/submodule
// knowledge, so it is unit-testable with a plain document double. app.js composes it with the
// real panel. Default state is CLOSED — the small launcher is the entry; the panel appears on
// click and hides again on the launcher/✕.

export const EDITOR_SOLVE_STYLE_ID = 'vemcad-editor-solve-entry-styles';
export const EDITOR_SOLVE_DOCK_ID = 'vemcad-solve-dock';
export const EDITOR_SOLVE_REGION_ID = 'vemcad-solve-region';

// Inject the entry's CSS once. No-op without a document head (resilient in headless/test docs).
export function ensureEditorSolveStyles(document) {
  if (!document?.head || typeof document.createElement !== 'function') return;
  if (typeof document.querySelector === 'function' && document.querySelector(`#${EDITOR_SOLVE_STYLE_ID}`)) return;
  const style = document.createElement('style');
  style.id = EDITOR_SOLVE_STYLE_ID;
  style.textContent = `
    .vemcad-solve-dock{position:fixed;right:16px;bottom:16px;z-index:40;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    .vemcad-solve-dock__launcher{min-height:36px;border:1px solid #114d7a;border-radius:8px;background:#114d7a;color:#fff;padding:8px 16px;font:inherit;font-weight:650;cursor:pointer;box-shadow:0 6px 18px rgb(15 23 42 / .18)}
    .vemcad-solve-dock[data-open="true"] .vemcad-solve-dock__launcher{display:none}
    .vemcad-solve-dock__card{width:min(340px,calc(100vw - 32px));max-height:min(70vh,560px);overflow:auto;background:#fff;border:1px solid #d8e0ee;border-radius:10px;box-shadow:0 12px 32px rgb(15 23 42 / .18)}
    .vemcad-solve-dock__bar{display:flex;align-items:center;justify-content:flex-end;padding:6px 8px;border-bottom:1px solid #eef1f6}
    .vemcad-solve-dock__close{border:0;background:transparent;font-size:20px;line-height:1;color:#5b6679;cursor:pointer;padding:2px 8px}
    .vemcad-solve-dock__close:hover{color:#1d2433}
    .vemcad-solve-region{padding:6px 14px 14px}
    .vemcad-solve-exports{padding:0 14px 12px;border-top:1px solid #eef1f6;margin-top:2px}
    .vemcad-solve-exports h3{margin:10px 0 8px;font-size:13px;font-weight:650;letter-spacing:0;color:#3d485c}
    .vemcad-solve-exports button{display:block;width:100%;min-height:32px;margin:0 0 6px;border:1px solid #c9d3e5;border-radius:6px;background:#fff;color:#1f2937;padding:6px 10px;font:inherit;cursor:pointer}
    .vemcad-solve-exports button:disabled{cursor:not-allowed;opacity:.55}
    .vemcad-solve-exports__status{min-height:18px;margin:2px 0 0;color:#5b6679;font-size:12px;line-height:1.4}
  `;
  document.head.appendChild(style);
}

// Build the entry chrome inside `host` and wire the toggle. Returns
//   { dock, launcher, card, regionRoot, open, close, toggle, isOpen, destroy }
// where `regionRoot` is the element the caller mounts the solve panel into. Returns null when
// the document/host cannot host elements (so the caller degrades gracefully). Idempotent: if a
// dock already exists in the document it is reused (its region cleared for a fresh mount).
export function buildSolveEntry({ document, host } = {}) {
  if (!document || typeof document.createElement !== 'function' || !host || typeof host.appendChild !== 'function') {
    return null;
  }
  ensureEditorSolveStyles(document);

  const existing = typeof document.getElementById === 'function' ? document.getElementById(EDITOR_SOLVE_DOCK_ID) : null;
  if (existing) {
    const region = document.getElementById(EDITOR_SOLVE_REGION_ID);
    if (region && typeof region.replaceChildren === 'function') region.replaceChildren();
    return wireEntry(existing, region);
  }

  const dock = document.createElement('div');
  dock.id = EDITOR_SOLVE_DOCK_ID;
  dock.className = 'vemcad-solve-dock';
  dock.dataset.open = 'false';

  const launcher = document.createElement('button');
  launcher.type = 'button';
  launcher.className = 'vemcad-solve-dock__launcher';
  launcher.textContent = 'Solve';
  launcher.setAttribute('aria-expanded', 'false');
  launcher.setAttribute('aria-controls', EDITOR_SOLVE_REGION_ID);
  dock.appendChild(launcher);

  const card = document.createElement('section');
  card.className = 'vemcad-solve-dock__card';
  card.hidden = true;
  dock.appendChild(card);

  const bar = document.createElement('header');
  bar.className = 'vemcad-solve-dock__bar';
  const close = document.createElement('button');
  close.type = 'button';
  close.className = 'vemcad-solve-dock__close';
  close.textContent = '×';
  close.setAttribute('aria-label', 'Close solver');
  bar.appendChild(close);
  card.appendChild(bar);

  const regionRoot = document.createElement('div');
  regionRoot.id = EDITOR_SOLVE_REGION_ID;
  regionRoot.className = 'vemcad-solve-region';
  card.appendChild(regionRoot);

  host.appendChild(dock);
  return wireEntry(dock, regionRoot);
}

// Attach open/close behavior to a dock element and return the handle. Split out so the
// idempotent (reuse-existing) path shares the exact same wiring.
function wireEntry(dock, regionRoot) {
  const launcher = dock.querySelector?.('.vemcad-solve-dock__launcher') ?? null;
  const card = dock.querySelector?.('.vemcad-solve-dock__card') ?? null;
  const close = dock.querySelector?.('.vemcad-solve-dock__close') ?? null;

  const isOpen = () => dock.dataset.open === 'true';
  const setOpen = (open) => {
    dock.dataset.open = open ? 'true' : 'false';
    if (card) card.hidden = !open;
    launcher?.setAttribute?.('aria-expanded', open ? 'true' : 'false');
  };
  const open = () => setOpen(true);
  const closeFn = () => setOpen(false);
  const toggle = () => setOpen(!isOpen());

  // Bind once: the idempotent reuse path must not stack a second pair of listeners (which in a
  // real DOM would double-fire the toggle). New closures are fine — they mutate the same nodes.
  if (dock.dataset.wired !== 'true') {
    launcher?.addEventListener?.('click', toggle);
    close?.addEventListener?.('click', closeFn);
    dock.dataset.wired = 'true';
  }

  return { dock, launcher, card, regionRoot, open, close: closeFn, toggle, isOpen };
}

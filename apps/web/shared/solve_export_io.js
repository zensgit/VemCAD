// Shared DOM IO for solve exports — clipboard copy + JSON file download — so the demo and the
// editor use the SAME copy/download path (the content shapes already live in solve_exports.js).
// Kept separate from solve_exports.js so that module stays pure; this one is the DOM-touching half.
// Each takes a `document` (the editor passes globalThis.document; the demo passes
// root.ownerDocument) and falls back to globals, so it works in either host.

// Copy text to the clipboard, with a hidden-textarea fallback for contexts that expose the
// Clipboard API but deny it (local/embedded). Throws when no path is available.
export async function copyText({ document, text } = {}) {
  const doc = document ?? globalThis.document;
  const win = doc?.defaultView ?? globalThis.window;
  const clipboard = win?.navigator?.clipboard ?? globalThis.navigator?.clipboard;
  if (clipboard && typeof clipboard.writeText === 'function') {
    try {
      await clipboard.writeText(text);
      return;
    } catch {
      // fall through to the textarea path
    }
  }
  if (doc?.body && typeof doc.createElement === 'function' && typeof doc.execCommand === 'function') {
    const textarea = doc.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    doc.body.appendChild(textarea);
    textarea.select();
    const copied = doc.execCommand('copy');
    doc.body.removeChild(textarea);
    if (copied) return;
  }
  throw new Error('clipboard is unavailable');
}

// Download `value` (any JSON-serializable object) as a pretty-printed .json file. Throws when the
// host can't synthesize a download (no Blob / object URL).
export async function downloadJson({ document, value, filename } = {}) {
  const doc = document ?? globalThis.document;
  const win = doc?.defaultView ?? globalThis.window;
  if (!doc?.body || typeof doc.createElement !== 'function' || !win?.Blob || !win?.URL?.createObjectURL) {
    throw new Error('download is unavailable');
  }
  const blob = new win.Blob([`${JSON.stringify(value, null, 2)}\n`], { type: 'application/json' });
  const url = win.URL.createObjectURL(blob);
  const link = doc.createElement('a');
  link.href = url;
  link.download = filename;
  link.rel = 'noreferrer';
  doc.body.appendChild(link);
  try {
    link.click();
  } finally {
    doc.body.removeChild(link);
    win.setTimeout?.(() => win.URL.revokeObjectURL(url), 0);
  }
}

// Open a file picker and resolve the parsed JSON of the chosen .json file. Rejects with
// 'project import canceled' if the user cancels, or a parse/read error otherwise. The hidden
// input is always cleaned up.
export function readJsonFile({ document } = {}) {
  const doc = document ?? globalThis.document;
  if (!doc?.body || typeof doc.createElement !== 'function') {
    return Promise.reject(new Error('file picker is unavailable'));
  }
  return new Promise((resolve, reject) => {
    const input = doc.createElement('input');
    input.type = 'file';
    input.accept = '.json,application/json';
    input.style.position = 'fixed';
    input.style.opacity = '0';
    input.style.pointerEvents = 'none';
    let settled = false;
    const cleanup = () => { if (input.parentNode) input.parentNode.removeChild(input); };
    const finish = (fn, value) => { if (settled) return; settled = true; cleanup(); fn(value); };

    input.addEventListener('change', async () => {
      try {
        const file = input.files?.[0];
        if (!file || typeof file.text !== 'function') throw new Error('no project file selected');
        finish(resolve, JSON.parse(await file.text()));
      } catch (err) {
        finish(reject, err);
      }
    });
    input.addEventListener?.('cancel', () => finish(reject, new Error('project import canceled')));
    doc.body.appendChild(input);
    input.click();
  });
}

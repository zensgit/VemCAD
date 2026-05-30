#!/usr/bin/env node
import { startStaticServer } from './serve_product_web.mjs';

function assertIncludes(text, needle, label) {
  if (!text.includes(needle)) {
    throw new Error(`${label} missing ${needle}`);
  }
}

async function fetchText(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} returned HTTP ${response.status}`);
  }
  return response.text();
}

const started = await startStaticServer({ host: '127.0.0.1', port: 0 });

try {
  const base = `http://${started.host}:${started.server.address().port}`;
  const indexUrl = `${base}/apps/web/index.html?mode=solve-demo`;
  const indexHtml = await fetchText(indexUrl);
  assertIncludes(indexHtml, 'bootstrapVemcadWebApp', 'index.html');
  assertIncludes(indexHtml, 'cad-editor-root', 'index.html');

  const appJs = await fetchText(`${base}/apps/web/app.js`);
  assertIncludes(appJs, 'solve-demo', 'app.js');
  assertIncludes(appJs, 'mountSolveWorkbenchDemo', 'app.js');

  const demoPageJs = await fetchText(`${base}/apps/web/workbench/solver/demo_page.js`);
  assertIncludes(demoPageJs, 'VemCAD Solve Workbench', 'demo_page.js');
  assertIncludes(demoPageJs, 'renderCadgfPreviewCanvas', 'demo_page.js');

  const previewCanvasJs = await fetchText(`${base}/apps/web/workbench/solver/preview_canvas.js`);
  assertIncludes(previewCanvasJs, 'Solved geometry preview', 'preview_canvas.js');

  console.log(`solve-demo smoke PASS: ${indexUrl}`);
} finally {
  await started.stop();
}

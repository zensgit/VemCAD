#!/usr/bin/env node
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { startStaticServer } from './serve_product_web.mjs';
import { SOLVE_WORKBENCH_DEMOS } from '../apps/web/workbench/solver/demo_projects.js';

const require = createRequire(import.meta.url);

const CASES = [
  {
    id: 'solvableLine',
    status: 'Solved',
    detail: /state=underconstrained/,
    summary: /state=underconstrained/,
    diagnostics: /^diagnostics=1$/,
    preview: 'svg',
  },
  {
    id: 'conflictingLine',
    status: 'Blocked',
    detail: /state=overconstrained/,
    summary: /state=overconstrained/,
    diagnostics: /^diagnostics=1$/,
    preview: 'empty',
  },
  {
    id: 'passthroughUnsupported',
    status: 'Solved',
    detail: /iters=0/,
    summary: /iters=0/,
    diagnostics: /^diagnostics=2$/,
    preview: 'empty',
  },
];

function loadPlaywright() {
  try {
    return require('playwright');
  } catch (err) {
    const hint = [
      'Playwright is required for the browser solve-demo smoke.',
      'Install it locally or expose an existing install with NODE_PATH.',
      'Example: NODE_PATH=/path/to/node_modules npm run smoke:solve-demo:browser',
    ].join('\n');
    throw new Error(`${hint}\n\n${err?.message ?? String(err)}`);
  }
}

async function textOf(page, selector) {
  return (await page.locator(selector).textContent())?.trim() ?? '';
}

async function assertText(page, selector, expected, label) {
  const actual = await textOf(page, selector);
  if (actual !== expected) {
    throw new Error(`${label}: expected "${expected}", got "${actual}"`);
  }
}

async function assertMatches(page, selector, expected, label) {
  const actual = await textOf(page, selector);
  if (!expected.test(actual)) {
    throw new Error(`${label}: expected ${expected}, got "${actual}"`);
  }
}

async function assertPreview(page, expected, label) {
  const svgCount = await page.locator('.vemcad-preview-canvas').count();
  const emptyCount = await page.locator('.vemcad-preview-canvas__empty').count();
  if (expected === 'svg' && svgCount !== 1) {
    throw new Error(`${label}: expected one solved SVG preview, got ${svgCount}`);
  }
  if (expected === 'empty' && emptyCount !== 1) {
    throw new Error(`${label}: expected one empty preview, got ${emptyCount}`);
  }
}

async function assertVisibleBox(page, selector, label) {
  const box = await page.locator(selector).evaluate((el) => {
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return {
      width: rect.width,
      height: rect.height,
      display: style.display,
      visibility: style.visibility,
    };
  });
  if (box.width <= 0 || box.height <= 0 || box.display === 'none' || box.visibility === 'hidden') {
    throw new Error(`${label}: element is not visibly laid out (${JSON.stringify(box)})`);
  }
}

async function maybeScreenshot(page, screenshotDir, id) {
  if (!screenshotDir) return null;
  const screenshotPath = path.join(screenshotDir, `${id}.png`);
  try {
    await page.locator('.vemcad-solve-demo').screenshot({ path: screenshotPath, timeout: 5000 });
    return screenshotPath;
  } catch (err) {
    console.warn(`screenshot skipped for ${id}: ${err?.message ?? String(err)}`);
    return null;
  }
}

async function verifyCase({ page, base, screenshotDir, spec }) {
  const url = `${base}/apps/web/index.html?mode=solve-demo&demo=${encodeURIComponent(spec.id)}`;
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForSelector('.vemcad-solve-panel__status');

  await assertText(page, '.vemcad-solve-demo__tab[data-active="true"]', labelFor(spec.id), `${spec.id} active tab`);
  await assertText(page, '.vemcad-solve-panel__status', spec.status, `${spec.id} status`);
  await assertMatches(page, '.vemcad-solve-panel__details', spec.detail, `${spec.id} details`);
  await assertMatches(page, '.vemcad-solve-demo__solve-summary', spec.summary, `${spec.id} meta summary`);
  await assertMatches(page, '.vemcad-solve-demo__diagnostic-count', spec.diagnostics, `${spec.id} diagnostic count`);
  await assertMatches(page, '.vemcad-solve-demo__share', new RegExp(`demo=${spec.id}`), `${spec.id} share link`);
  await assertText(page, '.vemcad-solve-demo__export', 'Export Project JSON', `${spec.id} export button`);
  await assertText(page, '.vemcad-solve-demo__export-status', 'Ready to export project.', `${spec.id} export status`);
  await assertText(page, '.vemcad-solve-demo__import', 'Import Project JSON', `${spec.id} import button`);
  await assertText(page, '.vemcad-solve-demo__import-status', 'Ready to import project.', `${spec.id} import status`);
  await assertText(page, '.vemcad-solve-demo__copy', 'Copy link', `${spec.id} copy button`);
  await assertText(page, '.vemcad-solve-demo__copy-status', 'Ready to copy link.', `${spec.id} copy status`);
  await assertPreview(page, spec.preview, spec.id);
  await assertVisibleBox(page, '.vemcad-solve-demo__content', `${spec.id} content`);
  if (spec.preview === 'svg') {
    await assertVisibleBox(page, '.vemcad-preview-canvas', `${spec.id} preview`);
  }
  return maybeScreenshot(page, screenshotDir, spec.id);
}

async function verifyImportProject({ page, base, screenshotDir }) {
  const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'vemcad-solve-demo-import-'));
  const projectPath = path.join(tmpDir, 'solvable-line.vemcad-project.json');
  await fs.writeFile(projectPath, `${JSON.stringify(SOLVE_WORKBENCH_DEMOS.solvableLine, null, 2)}\n`, 'utf8');

  const url = `${base}/apps/web/index.html?mode=solve-demo&demo=conflictingLine`;
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForSelector('.vemcad-solve-demo__import');
  const chooserPromise = page.waitForEvent('filechooser', { timeout: 5000 });
  await page.locator('.vemcad-solve-demo__import').click();
  const chooser = await chooserPromise;
  await chooser.setFiles(projectPath);

  await page.waitForSelector('.vemcad-solve-demo__tab[data-demo-id="importedProject"][data-active="true"]');
  await assertText(page, '.vemcad-solve-demo__tab[data-active="true"]', 'Imported', 'imported active tab');
  await assertText(page, '.vemcad-solve-demo__import-status', 'Project JSON imported.', 'import status after file picker');
  await assertMatches(page, '.vemcad-solve-demo__summary', /id=demo-solvable-line/, 'imported project summary');
  await assertText(page, '.vemcad-solve-demo__share', 'Imported project is local. Export JSON to share.', 'imported share text');
  await assertText(page, '.vemcad-solve-demo__copy-status', 'No share link for imported project.', 'imported copy status');
  await assertText(page, '.vemcad-solve-panel__status', 'Solved', 'imported solve status');
  await assertPreview(page, 'svg', 'imported project preview');

  try {
    return await maybeScreenshot(page, screenshotDir, 'importedProject');
  } finally {
    await fs.rm(tmpDir, { recursive: true, force: true });
  }
}

function labelFor(id) {
  if (id === 'solvableLine') return 'Solvable';
  if (id === 'conflictingLine') return 'Conflict';
  if (id === 'passthroughUnsupported') return 'Passthrough';
  return id;
}

const { chromium } = loadPlaywright();
const channel = process.env.PLAYWRIGHT_BROWSER_CHANNEL || 'chrome';
const screenshotDir = process.env.SOLVE_DEMO_SCREENSHOT_DIR
  ? path.resolve(process.env.SOLVE_DEMO_SCREENSHOT_DIR)
  : null;

const started = await startStaticServer({ host: '127.0.0.1', port: 0 });
let browser = null;

try {
  browser = await chromium.launch({ headless: true, channel });
  const page = await browser.newPage({ viewport: { width: 1280, height: 820 } });
  const base = `http://${started.host}:${started.server.address().port}`;
  const screenshots = [];

  for (const spec of CASES) {
    const screenshot = await verifyCase({ page, base, screenshotDir, spec });
    if (screenshot) screenshots.push(screenshot);
  }
  const importScreenshot = await verifyImportProject({ page, base, screenshotDir });
  if (importScreenshot) screenshots.push(importScreenshot);

  console.log('solve-demo browser smoke PASS');
  if (screenshots.length) {
    console.log(`screenshots: ${screenshotDir}`);
    for (const file of screenshots) console.log(`- ${file}`);
  }
} finally {
  await browser?.close();
  await started.stop();
}

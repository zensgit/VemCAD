#!/usr/bin/env node
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const repoRoot = path.resolve(path.dirname(__filename), '..');

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
};

function optionValue(name, fallback) {
  const prefix = `${name}=`;
  const args = process.argv.slice(2);
  const index = args.findIndex((arg) => arg === name || arg.startsWith(prefix));
  if (index < 0) return fallback;
  const found = args[index];
  if (found === name) return args[index + 1] ?? 'true';
  return found.slice(prefix.length);
}

function safePathFor(urlPath, root) {
  let decoded;
  try {
    decoded = decodeURIComponent(urlPath);
  } catch {
    return null;
  }
  const relative = decoded === '/' ? '/apps/web/index.html' : decoded;
  const resolved = path.resolve(root, `.${relative}`);
  if (resolved !== root && !resolved.startsWith(`${root}${path.sep}`)) {
    return null;
  }
  return resolved;
}

export function createStaticServer({ root = repoRoot } = {}) {
  const staticRoot = path.resolve(root);
  return http.createServer((req, res) => {
    const url = new URL(req.url || '/', 'http://127.0.0.1');
    const filePath = safePathFor(url.pathname, staticRoot);
    if (!filePath) {
      res.writeHead(403).end('forbidden');
      return;
    }

    fs.readFile(filePath, (err, body) => {
      if (err) {
        res.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' }).end('not found');
        return;
      }
      res.writeHead(200, {
        'content-type': MIME_TYPES[path.extname(filePath)] || 'application/octet-stream',
        'cache-control': 'no-store',
        'x-vemcad-static-root': staticRoot,
      });
      res.end(body);
    });
  });
}

export async function startStaticServer({
  host = process.env.HOST || '127.0.0.1',
  port = Number(process.env.PORT || 4173),
} = {}) {
  const server = createStaticServer();
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, host, resolve);
  });
  const address = server.address();
  const actualPort = typeof address === 'object' && address ? address.port : port;
  return {
    server,
    host,
    port: actualPort,
    url: `http://${host}:${actualPort}/apps/web/index.html?mode=solve-demo`,
    stop: () => new Promise((resolve) => server.close(resolve)),
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const host = optionValue('--host', process.env.HOST || '127.0.0.1');
  const port = Number(optionValue('--port', process.env.PORT || '4173'));
  const started = await startStaticServer({ host, port });
  console.log(`VemCAD web dev server: ${started.url}`);
}

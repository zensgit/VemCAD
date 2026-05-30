function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function createSvgElement(document, tag) {
  if (typeof document.createElementNS === 'function') {
    return document.createElementNS('http://www.w3.org/2000/svg', tag);
  }
  return document.createElement(tag);
}

function isPoint(value) {
  return Array.isArray(value)
    && value.length >= 2
    && Number.isFinite(value[0])
    && Number.isFinite(value[1]);
}

function collectGeometry(entities = []) {
  const items = [];
  const points = [];
  for (const entity of entities) {
    if (isPoint(entity?.point)) {
      items.push({ kind: 'point', p: entity.point });
      points.push(entity.point);
    } else if (Array.isArray(entity?.line) && isPoint(entity.line[0]) && isPoint(entity.line[1])) {
      items.push({ kind: 'line', a: entity.line[0], b: entity.line[1] });
      points.push(entity.line[0], entity.line[1]);
    } else if (entity?.circle && isPoint(entity.circle.c) && Number.isFinite(entity.circle.r) && entity.circle.r > 0) {
      const { c, r } = entity.circle;
      items.push({ kind: 'circle', c, r });
      points.push([c[0] - r, c[1] - r], [c[0] + r, c[1] + r]);
    } else if (entity?.arc && isPoint(entity.arc.c) && Number.isFinite(entity.arc.r) && entity.arc.r > 0) {
      const { c, r } = entity.arc;
      items.push({ kind: 'circle', c, r });
      points.push([c[0] - r, c[1] - r], [c[0] + r, c[1] + r]);
    }
  }
  return { items, points };
}

function boundsFor(points) {
  if (!points.length) return null;
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const [x, y] of points) {
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  }
  const width = Math.max(1, maxX - minX);
  const height = Math.max(1, maxY - minY);
  const pad = Math.max(width, height) * 0.15 + 1;
  return {
    minX: minX - pad,
    minY: minY - pad,
    maxX: maxX + pad,
    maxY: maxY + pad,
    width: width + pad * 2,
    height: height + pad * 2,
  };
}

function setAttrs(el, attrs) {
  for (const [key, value] of Object.entries(attrs)) {
    el.setAttribute(key, String(value));
  }
}

function flipY(bounds, y) {
  return bounds.minY + bounds.maxY - y;
}

function appendLine(svg, document, bounds, a, b) {
  const line = createSvgElement(document, 'line');
  setAttrs(line, {
    x1: a[0],
    y1: flipY(bounds, a[1]),
    x2: b[0],
    y2: flipY(bounds, b[1]),
    class: 'vemcad-preview-canvas__line',
  });
  svg.appendChild(line);
}

function appendPoint(svg, document, bounds, p) {
  const circle = createSvgElement(document, 'circle');
  setAttrs(circle, {
    cx: p[0],
    cy: flipY(bounds, p[1]),
    r: Math.max(bounds.width, bounds.height) * 0.015,
    class: 'vemcad-preview-canvas__point',
  });
  svg.appendChild(circle);
}

function appendCircle(svg, document, bounds, c, r) {
  const circle = createSvgElement(document, 'circle');
  setAttrs(circle, {
    cx: c[0],
    cy: flipY(bounds, c[1]),
    r,
    class: 'vemcad-preview-canvas__circle',
  });
  svg.appendChild(circle);
}

export function renderCadgfPreviewCanvas({ root, cadgfDocument } = {}) {
  if (!root || typeof root.appendChild !== 'function') {
    throw new TypeError('root element is required');
  }
  clear(root);

  const entities = Array.isArray(cadgfDocument?.entities) ? cadgfDocument.entities : [];
  const { items, points } = collectGeometry(entities);
  if (!items.length) {
    const empty = root.ownerDocument.createElement('p');
    empty.className = 'vemcad-preview-canvas__empty';
    empty.textContent = 'No solved geometry preview.';
    root.appendChild(empty);
    return { entityCount: entities.length, drawableCount: 0, bounds: null };
  }

  const bounds = boundsFor(points);
  const svg = createSvgElement(root.ownerDocument, 'svg');
  setAttrs(svg, {
    class: 'vemcad-preview-canvas',
    viewBox: `${bounds.minX} ${bounds.minY} ${bounds.width} ${bounds.height}`,
    role: 'img',
    'aria-label': 'Solved geometry preview',
  });

  for (const item of items) {
    if (item.kind === 'line') appendLine(svg, root.ownerDocument, bounds, item.a, item.b);
    else if (item.kind === 'point') appendPoint(svg, root.ownerDocument, bounds, item.p);
    else if (item.kind === 'circle') appendCircle(svg, root.ownerDocument, bounds, item.c, item.r);
  }

  root.appendChild(svg);
  return { entityCount: entities.length, drawableCount: items.length, bounds };
}

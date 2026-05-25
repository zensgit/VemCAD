// Shared deterministic ordering + id-validation primitives for the Project
// Runtime. Centralizing these keeps one authoritative ordering rule across
// modules: the duplicate-id key MUST match the sort comparator's equality
//   compareIds(a, b) === 0  ⟺  String(a) === String(b)
// so duplicate detection and stable ordering can never disagree (the bug class
// behind the P2 finding). Use these instead of re-deriving the rule per module.

export function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

// Locale-independent (code-unit) comparison. Never `localeCompare`, which varies
// by environment locale and would break cross-machine determinism.
export function compareStrings(a, b) {
  return a < b ? -1 : a > b ? 1 : 0;
}

// Numeric ids compare numerically (0, 1, 2, 10); otherwise by string code-units.
export function compareIds(a, b) {
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  return compareStrings(String(a), String(b));
}

export function byId(a, b) {
  return compareIds(a?.id, b?.id);
}

// True when two ids denote the same record under the ordering rule
// (compareIds === 0, i.e. String(a) === String(b)). Use this for identity
// checks ("does this id already exist?") so they agree with sorting and
// duplicate detection — never a bare `===`, which would miss 0 vs "0".
export function sameId(a, b) {
  return compareIds(a, b) === 0;
}

// Validate that every record is an object with a present, unique id. Returns
// null when sound, else { code, message }. The caller supplies `errorCode` so
// each domain reports under its own code.
export function validateUniqueRecordIds(records, label, errorCode) {
  const seen = new Set();
  for (const record of records) {
    if (!isObject(record)) {
      return { code: errorCode, message: `${label} entries must be objects` };
    }
    const id = record.id;
    const hasUsableId =
      (typeof id === 'number' && Number.isFinite(id)) || (typeof id === 'string' && id.length > 0);
    if (!hasUsableId) {
      return { code: errorCode, message: `${label} entries require a finite numeric or non-empty string id` };
    }
    // Dedup key matches compareIds equality (numeric 0 and string "0" collide).
    const idKey = String(id);
    if (seen.has(idKey)) {
      return { code: errorCode, message: `${label} has a duplicate id: ${JSON.stringify(id)}` };
    }
    seen.add(idKey);
  }
  return null;
}

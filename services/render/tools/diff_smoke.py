#!/usr/bin/env python3
"""In-image smoke for POST /diff (the L1 version-diff path). Posts one DXF as
BOTH revisions (a self-diff) and asserts the service rendered twice, ran the
diff engine, and returned a PNG overlay marked comparable. Catches three
deploy regressions a unit test can't: the diff engine not copied into the
image (-> 501), numpy/Pillow missing from the image (-> 501), and the
render_cli -> overlay handoff failing in the Linux runtime.

Stdlib only (the image has no httpx). Usage:
    python3 diff_smoke.py http://127.0.0.1:8077 /tmp/sample.dxf
Exit 0 on a comparable PNG overlay; non-zero (with the response body) otherwise.
"""

import sys
import urllib.error
import urllib.request


def _multipart(dxf: bytes):
    boundary = "----vemcaddiffsmoke"
    pre = []
    for field in ("file_a", "file_b"):
        pre.append(
            ("--%s\r\n"
             'Content-Disposition: form-data; name="%s"; filename="%s.dxf"\r\n'
             "Content-Type: application/octet-stream\r\n\r\n" % (boundary, field, field)
             ).encode("utf-8")
        )
    # Closing delimiter with no trailing epilogue (a trailing CRLF makes strict
    # parsers warn "data after last boundary").
    body = (
        pre[0] + dxf + b"\r\n"
        + pre[1] + dxf + b"\r\n"
        + ("--%s--" % boundary).encode("utf-8")
    )
    return body, "multipart/form-data; boundary=%s" % boundary


def main(argv) -> int:
    if len(argv) != 3:
        print("usage: diff_smoke.py BASE_URL DXF_PATH", file=sys.stderr)
        return 2
    base, dxf_path = argv[1].rstrip("/"), argv[2]
    with open(dxf_path, "rb") as f:
        dxf = f.read()
    body, content_type = _multipart(dxf)
    url = base + "/diff?width=400&height=300&bg=white"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": content_type})
    try:
        resp = urllib.request.urlopen(req, timeout=60)
    except urllib.error.HTTPError as e:
        print("diff smoke FAILED: HTTP %d\n%s" % (e.code, e.read().decode("utf-8", "replace")))
        return 1
    except Exception as e:  # noqa: BLE001 — surface anything, this is a smoke
        print("diff smoke FAILED: %s" % e)
        return 1

    ct = resp.headers.get("Content-Type", "")
    comparable = resp.headers.get("X-Diff-Comparable", "")
    changed = resp.headers.get("X-Diff-Changed-Fraction", "")
    payload = resp.read()
    print("diff smoke: status=%d content-type=%s comparable=%s changed-fraction=%s bytes=%d"
          % (resp.status, ct, comparable, changed, len(payload)))
    ok = (resp.status == 200 and ct.startswith("image/png")
          and comparable == "true" and len(payload) > 1000)
    if not ok:
        print("diff smoke FAILED: expected a 200 image/png comparable overlay")
        return 1
    print("diff smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

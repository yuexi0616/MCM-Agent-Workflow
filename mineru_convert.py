"""
MinerU Cloud API — PDF to Markdown batch converter with post-processing.

Usage:
    python mineru_convert.py <pdf_directory> [--lang ch|en] [--token TOKEN]
    python mineru_convert.py <pdf_directory> --no-postprocess
"""

import argparse
import io
import re
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
API_BASE    = "https://mineru.net/api/v4"
BATCH_MAX   = 50
POLL_EVERY  = 10
MAX_WAIT    = 600
MAX_RETRIES = 3

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"}

DETAILS_RE = re.compile(
    r"<details>\s*<summary>(text_image|natural_image|flowchart)</summary>\s*\n(.*?)\n</details>",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Encoding: force stdout to utf-8 so Chinese / Unicode renders on Windows
# ---------------------------------------------------------------------------
def _setup_encoding():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
class MinerUClient:
    def __init__(self, token: str, lang: str = "en"):
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        })
        self.lang = lang

    def _request(self, method: str, path: str, **kwargs):
        url = f"{API_BASE}{path}"
        last_err = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.request(method, url, timeout=120, **kwargs)
                resp.raise_for_status()
                body = resp.json()
                if body.get("code") != 0:
                    raise RuntimeError(f"API error: {body.get('msg', body)}")
                return body
            except (requests.RequestException, RuntimeError) as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    wait = 2 ** attempt
                    print(f"  [retry {attempt}/{MAX_RETRIES} in {wait}s] {e}")
                    time.sleep(wait)
        raise last_err  # type: ignore[misc]

    # -- pipeline steps -------------------------------------------------------
    def create_batch(self, pdf_paths: list[Path]):
        payload = [
            {"name": p.name, "data_id": str(i)}
            for i, p in enumerate(pdf_paths)
        ]
        body = self._request("POST", "/file-urls/batch", json={
            "files": payload,
            "model_version": "vlm",
            "enable_formula": True,
            "enable_table": True,
            "language": self.lang,
        })
        return body["data"]["batch_id"], body["data"]["file_urls"]

    @staticmethod
    def upload_file(path: Path, url: str):
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with open(path, "rb") as fh:
                    put = requests.put(url, data=fh, timeout=300)
                    put.raise_for_status()
                return
            except requests.RequestException as e:
                if attempt == MAX_RETRIES:
                    raise
                time.sleep(2 ** attempt)

    def upload_batch(self, pdf_paths: list[Path], upload_urls: list[str]):
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {
                pool.submit(self.upload_file, p, u): p
                for p, u in zip(pdf_paths, upload_urls)
            }
            for fut in as_completed(futures):
                p = futures[fut]
                fut.result()  # raise on error
                print(f"  uploaded: {p.name}")

    def poll_batch(self, batch_id: str):
        print(f"  polling {batch_id} ...")
        elapsed = 0
        while elapsed < MAX_WAIT:
            time.sleep(POLL_EVERY)
            elapsed += POLL_EVERY
            body = self._request("GET", f"/extract-results/batch/{batch_id}")
            results = body["data"]["extract_result"]
            states = {r["state"] for r in results}
            summary = " | ".join(
                f"{s}={sum(1 for r in results if r['state'] == s)}"
                for s in sorted(states)
            )
            print(f"  [{elapsed:>3}s] {summary}")
            if all(r["state"] == "done" for r in results):
                return results
        raise TimeoutError(f"Batch {batch_id} timed out after {MAX_WAIT}s")

    def download_result(self, r: dict, pdf: Path):
        zip_url = r.get("full_zip_url")
        if not zip_url:
            print(f"  SKIP {pdf.name}: no zip_url")
            return
        resp = self.session.get(zip_url, timeout=120)
        resp.raise_for_status()
        _extract_zip(resp.content, pdf.parent, pdf.stem)
        print(f"  [OK] {pdf.name}")


# ---------------------------------------------------------------------------
# ZIP extraction
# ---------------------------------------------------------------------------
def _extract_zip(zip_bytes: bytes, out_dir: Path, base_name: str):
    images_dir = out_dir / "images"
    md_path = out_dir / f"{base_name}.md"
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for member in zf.namelist():
            if member.endswith("/"):
                continue
            suffix = Path(member).suffix.lower()
            if suffix == ".md":
                md_path.write_bytes(zf.read(member))
            elif suffix in IMAGE_EXTS:
                images_dir.mkdir(parents=True, exist_ok=True)
                (images_dir / Path(member).name).write_bytes(zf.read(member))


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------
def _strip_details(text: str) -> str:
    def _replace(m: re.Match) -> str:
        return m.group(2).strip()
    return DETAILS_RE.sub(_replace, text)


def postprocess_markdown(root: Path) -> int:
    changed = 0
    for fp in sorted(root.rglob("*.md")):
        original = fp.read_text(encoding="utf-8")
        cleaned = _strip_details(original)
        if cleaned != original:
            fp.write_text(cleaned, encoding="utf-8")
            print(f"  postprocess: {fp.relative_to(root)}")
            changed += 1
    return changed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    _setup_encoding()

    parser = argparse.ArgumentParser(description="MinerU PDF -> Markdown converter")
    parser.add_argument("directory", help="Root directory containing PDF files")
    parser.add_argument("--token", default="", help="MinerU API token")
    parser.add_argument("--lang", default="en", choices=["ch", "en", "japan", "korean"])
    parser.add_argument("--no-postprocess", action="store_true", help="Skip <details> cleanup")
    args = parser.parse_args()

    token = args.token or ""
    if not token:
        print("ERROR: provide --token or set MINERU_TOKEN env var")
        sys.exit(1)

    root = Path(args.directory)
    pdf_paths = sorted(root.rglob("*.pdf"))
    if not pdf_paths:
        print(f"No PDFs found under: {root}")
        sys.exit(0)

    print(f"Found {len(pdf_paths)} PDF(s)")

    client = MinerUClient(token=token, lang=args.lang)

    for batch in _chunked(pdf_paths, BATCH_MAX):
        print(f"\n--- Batch {len(batch)} file(s) ---")
        batch_id, urls = client.create_batch(batch)
        print(f"  batch_id = {batch_id}")
        client.upload_batch(batch, urls)
        results = client.poll_batch(batch_id)
        for r, p in zip(results, batch):
            client.download_result(r, p)

    if not args.no_postprocess:
        print()
        n = postprocess_markdown(root)
        print(f"  cleaned {n} file(s)")

    print("\nDone.")


def _chunked(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


if __name__ == "__main__":
    main()

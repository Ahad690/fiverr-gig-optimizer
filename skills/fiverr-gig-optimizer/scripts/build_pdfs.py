#!/usr/bin/env python3
"""build_pdfs.py — optional per-gig A4 PDFs via headless Chrome/Edge. FR15.

For each gig in gig-config.json, renders the editorial template
(assets/pdf-template.html) to a one-page A4 PDF using a headless Chromium
browser (Chrome or Edge). If no browser is found, prints a warning and exits 0
(the HTML catalog is unaffected). NEVER fails the run just because PDFs are off.

CLI:
    build_pdfs.py gig-config.json [--out-dir pdfs] [--template assets/pdf-template.html]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

CHROME_CANDIDATES = [
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
    "chrome", "msedge",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_browser():
    for cand in CHROME_CANDIDATES:
        if os.path.sep in cand or (os.altsep and os.altsep in cand):
            if os.path.exists(cand):
                return cand
        else:
            found = shutil.which(cand)
            if found:
                return found
    return None


def default_template():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "assets", "pdf-template.html")


def fill_template(template, gig, seller):
    img = gig.get("img", {})
    pricing = gig.get("pricing", {})
    rows = ""
    for tier in ("basic", "standard", "premium"):
        p = pricing.get(tier) or {}
        items = "".join(f"<li>{i}</li>" for i in (p.get("items") or []))
        rows += (f"<tr><td><b>{p.get('name', tier)}</b></td>"
                 f"<td>{('$' + str(p['price'])) if p.get('price') is not None else '—'}</td>"
                 f"<td>{p.get('del', '')}</td><td><ul>{items}</ul></td></tr>")
    repl = {
        "__ACCENT__": img.get("accent", "#06b6d4"),
        "__SELLER__": seller.get("name", ""),
        "__TITLE__": gig.get("title", ""),
        "__CAT__": gig.get("cat", ""),
        "__WHAT__": img.get("pdfWhat", ""),
        "__DESC__": gig.get("desc", ""),
        "__TIER_ROWS__": rows,
        "__TOOLS__": " • ".join(img.get("tools", [])),
    }
    out = template
    for k, v in repl.items():
        out = out.replace(k, str(v))
    return out


def render_pdf(browser, html_path, pdf_path):
    cmd = [
        browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}", f"file://{html_path}",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        return os.path.exists(pdf_path)
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"warning: PDF render failed for {pdf_path}: {exc}", file=sys.stderr)
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description="Optional per-gig A4 PDFs (headless Chrome).")
    ap.add_argument("config", help="Path to gig-config.json.")
    ap.add_argument("--out-dir", default="pdfs")
    ap.add_argument("--template", default=None)
    args = ap.parse_args(argv)

    browser = find_browser()
    if not browser:
        print("warning: no Chrome/Edge found — skipping PDF generation. "
              "The HTML catalog is unaffected.", file=sys.stderr)
        return 0

    with open(args.config, encoding="utf-8") as fh:
        config = json.load(fh)
    template_path = args.template or default_template()
    with open(template_path, encoding="utf-8") as fh:
        template = fh.read()

    os.makedirs(args.out_dir, exist_ok=True)
    seller = config.get("seller", {})
    made = 0
    for gig in config.get("gigs", []):
        html = fill_template(template, gig, seller)
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                         encoding="utf-8") as tmp:
            tmp.write(html)
            tmp_path = tmp.name
        pdf_path = os.path.abspath(os.path.join(args.out_dir, f"gig-{gig['id']}.pdf"))
        if render_pdf(browser, tmp_path, pdf_path):
            made += 1
        os.unlink(tmp_path)

    print(f"Wrote {made} PDF(s) to {args.out_dir}/ using {os.path.basename(browser)}.")
    import reminders
    reminders.contribution_reminder()
    return 0


if __name__ == "__main__":
    sys.exit(main())

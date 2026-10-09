"""REQ-048: the graph viewer exercised in a real browser.

A tiny fixture repository (two Python modules, one importing the other), one requirement, one failure-ledger entry and a
synthetic Arbiter report go through `omni graph build` and `omni graph view --all --mode 2d`; the page is opened with
file:// in headless Chromium through Playwright, and the Findings tab, the search results, the detail panel (source row
and breadcrumb), both trace buttons and the severity colour mode are driven and read back from the DOM.

The test skips itself unless `playwright.sync_api` imports, a Chromium can be launched, and the [graph] extra (tree-sitter)
that `omni graph build` needs is installed. CI runs it for real in the viewer-browser job. Run with:

    python3 -m unittest tests.test_viewer_browser -v
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from playwright.sync_api import Error as PlaywrightError, sync_playwright
except ImportError:  # pragma: no cover - the skip below says why
    sync_playwright = None  # type: ignore[assignment]
    PlaywrightError = Exception  # type: ignore[assignment,misc]

_HAS_GRAPH_EXTRA = importlib.util.find_spec("tree_sitter") is not None
TIMEOUT_MS = 10_000   # every wait is bounded; the whole test stays well under a minute

REGISTRY = {
    "version": "1.0.0",
    "requirement_id_prefix": "REQ",
    "requirements": [
        {"id": "REQ-001", "category": "Feature", "title": "Add numbers", "description": "d", "priority": "high",
         "status": "completed", "minimum_access_scope": ["src/app.py"], "acceptance_criteria": [],
         "validation_required": [], "documentation_required": [], "risk_notes": []},
    ],
}

LEDGER = {
    "version": "1.0.0",
    "failure_id_prefix": "FAIL",
    "failures": [
        {"id": "FAIL-001", "date": "2026-10-01", "title": "Function grew too long", "status": "open", "symptom": "s",
         "how_detected": "arbiter gate finding f:bbb222 during REQ-001", "affected": ["src/helper.py"]},
    ],
}

# The shape tests/test_graph_findings.py uses; the evidence field is never copied into the graph (REQ-043).
REPORT = {
    "schema_version": 1,
    "findings": [
        {"id": "f:aaa111", "rule_id": "arbiter/secrets.aws-access-key", "title": "Key in source", "dimension": "security",
         "severity": "high", "status": "new", "suppressed": False, "tags": ["secret", "req:REQ-001"],
         "location": {"path": "src/app.py", "start_line": 5, "logical": "", "repo_id": "root"}, "evidence": "E"},
        {"id": "f:bbb222", "rule_id": "arbiter/quality.long-function", "title": "Long function", "dimension": "quality",
         "severity": "low", "status": "existing", "suppressed": False, "tags": [],
         "location": {"path": "src/helper.py", "start_line": 2}, "evidence": "E"},
    ],
}

APP_PY = "import helper\n\n\ndef main():\n    return helper.add(1, 2)\n"   # line 5 sits inside main()
HELPER_PY = "def add(a, b):\n    return a + b\n"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def bundled_chromiums() -> list[Path]:
    """Chromium binaries Playwright has on this machine, newest build first, for when the installed package expects a
    different build than the one that is present (the browser is then launched by executable_path)."""
    roots = [os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "", str(Path.home() / ".cache" / "ms-playwright")]
    found: list[Path] = []
    for root in roots:
        base = Path(root)
        if not root or not base.is_dir():
            continue
        for pattern in ("chromium-*/chrome-linux*/chrome", "chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium",
                        "chromium_headless_shell-*/chrome-linux*/headless_shell"):
            found.extend(p for p in base.glob(pattern) if p.is_file())
    def build(p: Path) -> int:
        folder = next((part for part in p.parts if part.startswith("chromium")), "")
        m = re.search(r"-(\d+)$", folder)
        return int(m.group(1)) if m else 0
    return sorted(set(found), key=build, reverse=True)


def launch_chromium(playwright):
    """The default Chromium, else any bundled one; raises SkipTest when none launches."""
    errors: list[str] = []
    try:
        return playwright.chromium.launch()
    except PlaywrightError as exc:
        errors.append(str(exc).splitlines()[0])
    for exe in bundled_chromiums():
        try:
            return playwright.chromium.launch(executable_path=str(exe))
        except PlaywrightError as exc:
            errors.append(f"{exe}: {str(exc).splitlines()[0]}")
    raise unittest.SkipTest("no Chromium could be launched: " + "; ".join(errors))


def hex_to_rgb(color: str) -> str:
    """'#ff5c5c' -> 'rgb(255, 92, 92)', the form a computed inline style reads back as."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgb({r}, {g}, {b})"


@unittest.skipUnless(sync_playwright, "playwright is not installed (pip install playwright)")
@unittest.skipUnless(_HAS_GRAPH_EXTRA, "needs the [graph] extra (tree-sitter) for omni graph build; the viewer-browser CI job installs it")
class TestViewerInChromium(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        write(self.root / "src/app.py", APP_PY)
        write(self.root / "src/helper.py", HELPER_PY)
        write(self.root / ".ai/requirements/requirements.json", json.dumps(REGISTRY))
        write(self.root / ".ai/failures/failure-ledger.json", json.dumps(LEDGER))
        write(self.root / "arbiter-out/omni-gate/report.json", json.dumps(REPORT))   # the default report path omni graph build reads

    def omni(self, *args: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run([sys.executable, str(ROOT / "make_ai.py"), *args], cwd=self.root, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, f"omni {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}")
        return result

    def test_a_finding_is_traced_to_its_requirement_and_its_failure_in_the_browser(self) -> None:
        self.omni("graph", "build")
        self.omni("graph", "view", "--all", "--mode", "2d")
        page_path = self.root / ".ai/project-graph.html"
        self.assertTrue(page_path.is_file())
        meta = json.loads(re.search(r'id="omni-data" type="application/json">(.*?)</script>', page_path.read_text(encoding="utf-8"), re.S).group(1))["meta"]
        finding_colors = meta["finding_colors"]
        self.assertIn("security", finding_colors)

        console: list[str] = []
        with sync_playwright() as playwright:
            browser = launch_chromium(playwright)
            try:
                page = browser.new_page()
                page.set_default_timeout(TIMEOUT_MS)
                page.on("console", lambda m: m.type in ("error", "warning") and console.append(f"console.{m.type}: {m.text}"))
                page.on("pageerror", lambda e: console.append(f"pageerror: {e}"))
                page.goto(page_path.resolve().as_uri())

                # 1. the page booted into the overview and offers a Findings tab, because the graph holds finding nodes
                page.wait_for_selector("#views button.vtab")
                tabs = [t.inner_text().splitlines()[0] for t in page.query_selector_all("#views button.vtab")]
                self.assertIn("Findings", tabs)
                self.assertEqual(page.evaluate("window.omniGraphViewer.state().view"), "overview")

                # 2. switch to the Findings view: it colours by dimension, and the key strip uses meta.finding_colors
                page.click("#views button.vtab:has-text('Findings')")
                page.wait_for_selector("#views button.vtab.on:has-text('Findings')")
                self.assertEqual(page.evaluate("window.omniGraphViewer.state().view"), "findings")
                self.assertEqual(page.input_value("#colormode"), "dimension")
                self.assertEqual(page.evaluate("window.omniGraphViewer.state().colorMode"), "dimension")
                self.assertEqual(page.evaluate("window.omniGraphViewer.nodeColor('finding:f:aaa111')"), finding_colors["security"])
                self.assertEqual(page.evaluate("window.omniGraphViewer.nodeColor('finding:f:bbb222')"), finding_colors["quality"])
                chip = page.wait_for_selector("#chips .chip:has-text('security')")
                self.assertEqual(chip.query_selector("i").evaluate("e => e.style.background"), hex_to_rgb(finding_colors["security"]))

                # 3. the search lists both findings with the kind: prefix, and severity: narrows to one
                page.fill("#q", "kind:finding")
                page.wait_for_selector("#results .res:nth-child(2)")
                rows = page.query_selector_all("#results .res")
                self.assertEqual([r.query_selector(".nm").inner_text() for r in rows], ["f:aaa111", "f:bbb222"])
                self.assertEqual([r.query_selector(".r2").inner_text() for r in rows], ["Key in source", "Long function"])
                self.assertIn("2 matches", page.inner_text("#qinfo"))
                page.fill("#q", "severity:high")
                page.wait_for_selector("#results .res")
                page.wait_for_function("document.querySelectorAll('#results .res').length === 1")
                self.assertEqual(page.inner_text("#results .res .nm"), "f:aaa111")
                page.fill("#q", "kind:finding")
                page.wait_for_selector("#results .res:nth-child(2)")

                # 4. click the first finding: the detail panel shows path:line and the breadcrumb directory › file › symbol › finding
                page.click("#results .res:nth-child(1)")
                page.wait_for_selector("#detail h3:has-text('f:aaa111')")
                self.assertEqual(page.evaluate("window.omniGraphViewer.state().selected"), "finding:f:aaa111")
                self.assertIn("src/app.py:5", page.inner_text("#detail .where"))
                source_row = page.wait_for_selector("#detail h2:has-text('Finding') + .edge")
                self.assertEqual(source_row.query_selector(".t").inner_text(), "source")
                self.assertEqual(source_row.query_selector(".n").inner_text(), "src/app.py:5")
                self.assertIsNotNone(source_row.query_selector("a:has-text('open in editor')"))
                crumbs = [c.inner_text() for c in page.query_selector_all("#detail .crumbs button")]
                self.assertEqual(crumbs, ["src · file", "app · module", "main · function", "f:aaa111 · finding"])
                self.assertEqual(page.inner_text("#detail .crumbs button.cur"), "f:aaa111 · finding")
                detail = page.inner_text("#detail")
                for text in ("arbiter/secrets.aws-access-key", "security", "high", "Key in source"):
                    self.assertIn(text, detail)

                # 5. Trace to requirement: the trace steps and the bar over the picture name REQ-001
                page.click("#detail button:has-text('Trace to requirement')")
                page.wait_for_selector("#tsteps .step")
                steps = [s.inner_text().splitlines()[0] for s in page.query_selector_all("#tsteps .step")]
                self.assertEqual(steps, ["1. f:aaa111 (finding)", "2. REQ-001 (requirement)"])
                self.assertIn("cites", page.inner_text("#tsteps"))
                self.assertTrue(page.is_visible("#tracebar"))
                self.assertIn("f:aaa111 → REQ-001", page.inner_text("#tracebar"))
                self.assertEqual(page.evaluate("window.omniGraphViewer.state().path"), 2)

                # 6. the second finding's Trace to failure reaches the ledger entry whose how_detected names it
                page.click("#results .res:nth-child(2)")
                page.wait_for_selector("#detail h3:has-text('f:bbb222')")
                self.assertEqual(page.inner_text("#detail h2:has-text('Finding') + .edge .n"), "src/helper.py:2")
                self.assertEqual([c.inner_text() for c in page.query_selector_all("#detail .crumbs button")],
                                 ["src · file", "helper · module", "add · function", "f:bbb222 · finding"])
                page.click("#detail button:has-text('Trace to failure')")
                page.wait_for_function("document.querySelector('#tracebar').textContent.indexOf('FAIL-001') > -1")
                steps = [s.inner_text().splitlines()[0] for s in page.query_selector_all("#tsteps .step")]
                self.assertEqual(steps, ["1. f:bbb222 (finding)", "2. FAIL-001 (failure)"])
                self.assertIn("recorded_as", page.inner_text("#tsteps"))

                # 7. colour by severity: the node colour and the key strip switch from the dimension palette to the severity one
                page.select_option("#colormode", "severity")
                page.wait_for_selector("#chips .chip:has-text('high')")
                self.assertEqual(page.evaluate("window.omniGraphViewer.state().colorMode"), "severity")
                high = page.evaluate("window.omniGraphViewer.nodeColor('finding:f:aaa111')")
                low = page.evaluate("window.omniGraphViewer.nodeColor('finding:f:bbb222')")
                self.assertNotEqual(high, low)
                self.assertNotIn(high, finding_colors.values())   # severity colours are not the dimension palette
                self.assertEqual(page.query_selector("#chips .chip:has-text('high') i").evaluate("e => e.style.background"), hex_to_rgb(high))
                self.assertEqual(page.query_selector("#chips .chip:has-text('low') i").evaluate("e => e.style.background"), hex_to_rgb(low))
                self.assertIsNone(page.query_selector("#chips .chip:has-text('security')"))
                page.select_option("#colormode", "dimension")
                page.wait_for_selector("#chips .chip:has-text('security')")
                self.assertEqual(page.evaluate("window.omniGraphViewer.nodeColor('finding:f:aaa111')"), finding_colors["security"])
            finally:
                browser.close()
        self.assertEqual(console, [], "the viewer logged errors:\n" + "\n".join(console))


if __name__ == "__main__":
    unittest.main()

"""Static contract for the additive "AXA în chat" concept page (/chat).
The page must reuse the existing API and data, never store or link message content,
and draw the semaphore/scale only from analysis.ui.spectrum. The main UI stays untouched."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parent
POSITIVE_SAFETY = re.compile(r"\b(sigur|verificat|în siguranță|legitim|safe|garantat)\b", re.IGNORECASE)


class ChatPage(unittest.TestCase):
    js = (ROOT / "assets/chat.js").read_text(encoding="utf-8")
    html = (ROOT / "chat.html").read_text(encoding="utf-8")

    def test_uses_existing_endpoints_only(self):
        self.assertEqual(set(re.findall(r"'(/api/[\w-]+)'", self.js)), {"/api/analyze", "/api/analyze-image", "/api/status"})

    def test_privacy_and_links(self):
        # the only thing written is the GDPR consent record; display preferences are read only
        self.assertEqual(re.findall(r"setItem\((\w+)", self.js), ["CK"])
        self.assertNotRegex(self.js, r"href=\"\$\{[^}]*original_url")
        self.assertIn("const esc", self.js)
        self.assertNotRegex(self.js + self.html, r"style=\"")  # CSP style-src 'self'
        self.assertNotIn("googleapis", self.html)

    def test_semaphore_comes_only_from_the_adapter(self):
        self.assertIn("sp.status === 'placed'", self.js)
        self.assertNotRegex(self.js, r"risk_estimate\s*[<>]")  # no thresholds re-derived in the browser
        pills = re.search(r"const PILL = \{([^}]*)\}", self.js).group(1)
        self.assertIsNone(POSITIVE_SAFETY.search(pills), pills)

    def test_honest_framing(self):
        self.assertIn("nu un serviciu WhatsApp", self.html)
        self.assertIn("Google Gemini", self.html)
        self.assertNotIn("end-to-end", self.html + self.js)

    def test_routes_are_additive(self):
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn('@app.get("/chat"', main)
        self.assertIn('ASSETS = {"axa.css": "text/css; charset=utf-8", "app.js": "text/javascript; charset=utf-8",', main)
        self.assertIn("CHAT_ASSETS", main)


if __name__ == "__main__":
    unittest.main()

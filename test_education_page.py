"""Static contract for /education (AXA for Education "în curând" preview): additive route and
assets, honest framing, no network use, and the navigation entry on the main page."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parent


class EducationPage(unittest.TestCase):
    html = (ROOT / "education.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/education.js").read_text(encoding="utf-8")
    css = (ROOT / "assets/education.css").read_text(encoding="utf-8")
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    index = (ROOT / "index.html").read_text(encoding="utf-8")

    def test_route_and_allow_listed_assets(self):
        self.assertIn('@app.get("/education"', self.main)
        self.assertIn('"education.css": "text/css; charset=utf-8", "education.js": "text/javascript; charset=utf-8"', self.main)
        self.assertIn("script-src 'self'; style-src 'self'", self.main)  # CSP unchanged
        self.assertIn('href="/assets/education.css"', self.html)
        self.assertIn('src="/assets/education.js"', self.html)

    def test_no_network_no_inline_styles_no_external_resources(self):
        for banned in ("fetch(", "XMLHttpRequest", "sendBeacon", "/api/", "WebSocket"):
            self.assertNotIn(banned, self.js + self.html, banned)
        self.assertNotRegex(self.html + self.js, r"style=\"")
        self.assertNotRegex(self.html, r"(src|href)=\"https?://")
        self.assertEqual(set(re.findall(r"localStorage\.setItem\(k", self.js)), {"localStorage.setItem(k"})
        self.assertNotIn("app.js", self.html)  # the main page script is not loaded here

    def test_honest_framing(self):
        for phrase in ("În curând", "Previzualizare conceptuală", "Exemple fictive", "nu dovedește o campanie coordonată",
                       "Lecția nu spune că afirmația e falsă", "Nu verifică știri, nu identifică boți sau deepfake-uri"):
            self.assertIn(phrase, self.html, phrase)
        for banned in ("% șanse", "detectăm boți", "verificăm știri", "înscrie-te", "newsletter", "<form"):
            self.assertNotIn(banned, self.html.lower() if banned.islower() else self.html, banned)

    def test_navigation(self):
        nav = re.search(r'<nav class="nav"[^>]*>(.*?)</nav>', self.index, re.S).group(1)
        labels = re.findall(r">([^<]+)</a>", nav)
        self.assertEqual(labels, ["Verifică", "Semne de fraudă", "Confidențialitate", "AXA for Education"])
        self.assertIn('href="/education"', nav)
        edu_nav = re.search(r'<nav class="nav"[^>]*>(.*?)</nav>', self.html, re.S).group(1)
        self.assertIn('href="/education" aria-current="page"', edu_nav)
        for href in ("/#verifica", "/#semne", "/#confidentialitate"):
            self.assertIn(f'href="{href}"', edu_nav)
        self.assertNotRegex(edu_nav, r'href="#')  # no bare anchors that do not exist on this page

    def test_styles_are_scoped(self):
        css = re.sub(r"/\*.*?\*/", "", self.css, flags=re.S)
        css = re.sub(r"@media[^{]*\{", "", css)
        css = re.sub(r"@keyframes[^{]*\{[^{}]*\{[^}]*\}[^{}]*\{[^}]*\}\s*\}", "", css)
        selectors = [m.strip() for m in re.findall(r"([^{}]+)\{[^{}]*\}", css)]
        unscoped = [sel for sel in selectors if not all(p.strip().startswith(".edu") for p in sel.split(","))]
        self.assertEqual(unscoped, [])


if __name__ == "__main__":
    unittest.main()

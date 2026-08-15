from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
INDEX = FRONTEND / "index.html"
GLAZE = FRONTEND / "glaze.css"
STYLES = FRONTEND / "styles.css"
APP = FRONTEND / "app.js"


class FrontendParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.buttons_without_type: list[str] = []
        self.remote_refs: list[str] = []
        self.inline_handlers: list[str] = []
        self.html_lang = ""
        self.meta_names: set[str] = set()
        self.stylesheets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "html":
            self.html_lang = values.get("lang") or ""
        if "id" in values and values["id"]:
            self.ids.append(values["id"] or "")
        if tag == "button" and not values.get("type"):
            self.buttons_without_type.append(values.get("id") or "<unnamed>")
        if tag == "meta" and values.get("name"):
            self.meta_names.add((values["name"] or "").lower())
        if tag == "link" and values.get("rel") == "stylesheet" and values.get("href"):
            self.stylesheets.append(values["href"] or "")
        for key, value in attrs:
            if key.lower().startswith("on"):
                self.inline_handlers.append(f"{tag}[{key}]")
            if key in {"src", "href", "action"} and value and (
                value.startswith("http://")
                or value.startswith("https://")
                or value.startswith("//")
            ):
                self.remote_refs.append(value)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    for path in (INDEX, GLAZE, STYLES, APP):
        require(path.is_file(), f"Missing required frontend file: {path.relative_to(ROOT)}", errors)
    if errors:
        return finish(errors)

    html = INDEX.read_text(encoding="utf-8")
    glaze = GLAZE.read_text(encoding="utf-8")
    styles = STYLES.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")

    parser = FrontendParser()
    parser.feed(html)

    require(bool(parser.html_lang.strip()), "The HTML document must declare a language.", errors)
    require("description" in parser.meta_names, "Browser metadata must include a description.", errors)
    require("theme-color" in parser.meta_names, "Browser metadata must include theme-color.", errors)
    require("/assets/glaze.css" in parser.stylesheets, "index.html must load the shared Glaze UI layer.", errors)
    require("/assets/styles.css" in parser.stylesheets, "index.html must load Calendar-specific styles.", errors)

    duplicates = sorted({value for value in parser.ids if parser.ids.count(value) > 1})
    require(not duplicates, f"Duplicate HTML ids: {', '.join(duplicates)}", errors)
    require(not parser.buttons_without_type, f"Buttons without explicit type: {', '.join(parser.buttons_without_type)}", errors)
    require(not parser.remote_refs, f"External browser references are not allowed: {', '.join(parser.remote_refs)}", errors)
    require(not parser.inline_handlers, f"Inline event handlers are not allowed: {', '.join(parser.inline_handlers)}", errors)

    required_ids = {
        "appView", "calendarGrid", "calendarList", "calendarPanel", "eventDialog",
        "eventSearch", "monthView", "scheduleView", "scheduleList", "themeButton",
        "newEventButton", "selectAllButton", "selectNoneButton", "syncState",
        "loadingState", "emptyState", "todayEvents", "upcomingEvents", "confirmDialog",
    }
    missing_ids = sorted(required_ids - set(parser.ids))
    require(not missing_ids, f"Missing required Glaze UI controls: {', '.join(missing_ids)}", errors)

    for path, content in ((INDEX, html), (GLAZE, glaze), (STYLES, styles), (APP, app)):
        external = re.findall(r"https?://|(?<!:)//[A-Za-z0-9]", content)
        require(not external, f"External HTTP(S) dependency marker found in {path.relative_to(ROOT)}.", errors)

    required_tokens = (
        "--glaze-surface", "--glaze-accent", "--glaze-radius-lg",
        "--glaze-shadow-2", "--glaze-speed", "--glaze-text-soft",
    )
    for token in required_tokens:
        require(token in glaze, f"Shared Glaze token is missing: {token}", errors)

    require(':root[data-theme="dark"]' in glaze, "Glaze UI must define an explicit dark theme.", errors)
    require("prefers-color-scheme: dark" in glaze, "Glaze UI must support system dark appearance.", errors)
    require("prefers-reduced-motion: reduce" in glaze, "Glaze UI must support reduced motion.", errors)
    require("prefers-reduced-transparency: reduce" in glaze, "Glaze UI must support reduced transparency.", errors)
    require(".glaze-surface" in glaze, "Shared Glaze surface component is missing.", errors)
    require(".glaze-button" in glaze, "Shared Glaze button component is missing.", errors)
    require(".mobile-action-bar" in styles, "Calendar mobile action navigation is missing.", errors)
    require("@media (max-width: 780px)" in styles, "Calendar must include an adaptive mobile breakpoint.", errors)

    js_ids = set(re.findall(r'\$\(["\']([A-Za-z0-9_-]+)["\']\)', app))
    missing_js_ids = sorted(js_ids - set(parser.ids))
    require(not missing_js_ids, f"JavaScript references missing HTML ids: {', '.join(missing_js_ids)}", errors)

    forbidden_js = {
        "innerHTML": "Use DOM construction instead of innerHTML.",
        "eval(": "eval is not permitted in the frontend.",
        "new Function": "Dynamic Function construction is not permitted.",
    }
    for marker, message in forbidden_js.items():
        require(marker not in app, message, errors)

    require('"schedule"' in app and "renderSchedule" in app, "Schedule view functionality is missing.", errors)
    require("eventSearch" in app and "filteredEvents" in app, "Local event search functionality is missing.", errors)
    require("goreecloud-calendar-theme" in app, "Named appearance preference storage is missing.", errors)

    return finish(errors)


def finish(errors: list[str]) -> int:
    if errors:
        print("Frontend Glaze UI structural validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Frontend Glaze UI structural validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

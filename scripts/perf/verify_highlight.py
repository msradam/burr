"""Assert click/hover highlighting works in the graph pane. Usage: verify_highlight.py <label>"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

INDEX = Path("/Users/amsrahman/burr/burr/tracking/server/build/index.html").read_text()
LABEL = sys.argv[1]

CLICK_ACTION = "decide_mode"
HOVER_ACTION = "check_safety"


def node_classes(page, action):
    node = page.locator(f".react-flow__node:has-text('{action}')").first
    return node.get_by_text(action, exact=True).get_attribute("class") or ""


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1200})
    page.route(
        "**/*",
        lambda route: route.fulfill(status=200, content_type="text/html", body=INDEX)
        if route.request.resource_type == "document"
        else route.continue_(),
    )
    page.goto("http://localhost:7241/project/demo_chatbot/null/chat-1-giraffe")
    page.wait_for_load_state("networkidle")
    for _ in range(30):
        if page.locator(".react-flow__node").count() > 0:
            break
        page.wait_for_timeout(1000)
    page.wait_for_timeout(2000)

    before = node_classes(page, CLICK_ACTION)
    page.locator(f"tr:has-text('{CLICK_ACTION}')").first.click()
    page.wait_for_timeout(500)
    after_click = node_classes(page, CLICK_ACTION)

    page.locator(f"tr:has-text('{HOVER_ACTION}')").first.hover()
    page.wait_for_timeout(500)
    hover_cls = node_classes(page, HOVER_ACTION)

    results = {
        "label": LABEL,
        "click_highlight_applied": "text-white" in after_click and "text-white" not in before,
        "click_border": "border-dwlightblue/50" in after_click,
        "hover_opacity_applied": "opacity-50" in hover_cls,
        "before": before.strip(),
        "after_click": after_click.strip(),
        "hover": hover_cls.strip(),
    }
    for k, v in results.items():
        print(f"{k}: {v}")
    page.screenshot(path=f"verify_{LABEL}.png", timeout=10000)
    browser.close()

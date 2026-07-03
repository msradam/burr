"""Screenshot the graph pane of a Burr app. Usage: shot.py <project> <app_id> <out.png>"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

INDEX = Path("/Users/amsrahman/burr/burr/tracking/server/build/index.html").read_text()
PROJECT, APP_ID, OUT = sys.argv[1], sys.argv[2], sys.argv[3]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1200})
    page.route(
        "**/*",
        lambda route: route.fulfill(status=200, content_type="text/html", body=INDEX)
        if route.request.resource_type == "document"
        else route.continue_(),
    )
    page.goto(f"http://localhost:7241/project/{PROJECT}/null/{APP_ID}")
    page.wait_for_load_state("networkidle")
    for _ in range(60):
        if page.locator(".react-flow__node").count() > 0:
            break
        page.wait_for_timeout(1000)
    page.wait_for_timeout(4000)
    page.locator(".react-flow").first.screenshot(path=OUT, timeout=15000)
    print(OUT, "written,", page.locator(".react-flow__node").count(), "nodes")
    browser.close()

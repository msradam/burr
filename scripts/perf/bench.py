"""Measure Burr UI graph interaction latency for one bench app.

Usage: python bench.py <app_id>
Appends a result line to bench_results.jsonl and writes bench_<app>.cpuprofile.
Run under `timeout` -- large graphs can hang the renderer outright.
"""

import json
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from playwright.sync_api import sync_playwright

INDEX = Path(
    os.environ.get(
        "BURR_UI_INDEX",
        "/Users/amsrahman/.local/share/uv/tools/burr/lib/python3.14/site-packages/burr/tracking/server/build/index.html",
    )
).read_text()

APP_ID = sys.argv[1]
N_SAMPLES = 12

MEASURE_JS = """
([el, eventType]) => new Promise((resolve) => {
  const t0 = performance.now();
  el.dispatchEvent(new MouseEvent(eventType, { bubbles: true, cancelable: true }));
  requestAnimationFrame(() => requestAnimationFrame(() => resolve(performance.now() - t0)));
})
"""


def emit(result):
    with open("bench_results.jsonl", "a") as f:
        f.write(json.dumps(result) + "\n")
    print(json.dumps(result))


def stats(xs):
    return {
        "median": round(statistics.median(xs), 1),
        "p95": round(sorted(xs)[int(0.95 * (len(xs) - 1))], 1),
        "max": round(max(xs), 1),
    }


def top_functions(profile, n=12):
    nodes = {node["id"]: node for node in profile["nodes"]}
    self_us = defaultdict(int)
    samples, deltas = profile["samples"], profile["timeDeltas"]
    for node_id, dt in zip(samples, deltas):
        fn = nodes[node_id]["callFrame"]["functionName"] or "(anonymous)"
        self_us[fn] += dt
    total = sum(self_us.values()) or 1
    return [
        {"fn": fn, "self_ms": round(us / 1000, 1), "pct": round(100 * us / total, 1)}
        for fn, us in sorted(self_us.items(), key=lambda kv: -kv[1])[:n]
    ]


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1200})
    # ponytail: workaround for apache/burr#809 (starlette 1.0 breaks the template route)
    page.route(
        "**/*",
        lambda route: (
            route.fulfill(status=200, content_type="text/html", body=INDEX)
            if route.request.resource_type == "document"
            else route.continue_()
        ),
    )
    import time

    t_nav = time.monotonic()
    page.goto(f"http://localhost:7241/project/ui-perf-bench/null/{APP_ID}")
    page.wait_for_load_state("networkidle")
    for _ in range(60):
        if page.locator(".react-flow__node").count() > 0:
            break
        page.wait_for_timeout(1000)
    else:
        emit({"app": APP_ID, "error": "graph never rendered in 60s"})
        sys.exit(1)
    render_s = round(time.monotonic() - t_nav, 1)
    page.wait_for_timeout(2000)

    n_nodes = page.locator(".react-flow__node").count()
    n_edges = page.locator(".react-flow__edge").count()

    rows = page.locator("tr", has_text="step_")
    n_rows = rows.count()
    if n_rows == 0:
        emit({"app": APP_ID, "error": "no step rows"})
        sys.exit(1)

    cdp = page.context.new_cdp_session(page)
    cdp.send("Profiler.enable")
    cdp.send("Profiler.start")

    idxs = [int(i * (n_rows - 1) / (N_SAMPLES - 1)) for i in range(N_SAMPLES)]
    clicks, hovers = [], []
    for i in idxs:
        row = rows.nth(i)
        row.scroll_into_view_if_needed()
        handle = row.element_handle()
        hovers.append(page.evaluate(MEASURE_JS, [handle, "mouseover"]))
        clicks.append(page.evaluate(MEASURE_JS, [handle, "click"]))
        page.wait_for_timeout(50)

    profile = cdp.send("Profiler.stop")["profile"]
    Path(f"bench_{APP_ID}.cpuprofile").write_text(json.dumps(profile))

    emit(
        {
            "app": APP_ID,
            "nodes": n_nodes,
            "edges": n_edges,
            "initial_render_s": render_s,
            "click_ms": stats(clicks),
            "hover_ms": stats(hovers),
            "top_functions": top_functions(profile),
        }
    )
    browser.close()

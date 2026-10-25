"""Replay public URL probes through a local ASGI prefix/forwarding model."""

import argparse
import asyncio
import html
import importlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

PROBE_TIMEOUT_SECONDS = 5


def demo_app():
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/items/")
    async def items():
        return {"items": ["synthetic-part-17"]}

    return app


def prefix(value):
    if not isinstance(value, str) or (
        value
        and (
            not value.startswith("/")
            or value.endswith("/")
            or "//" in value
            or any(x in value for x in ("?", "#", "%", "\\"))
        )
    ):
        raise ValueError(
            "prefix must be empty or a plain absolute path without a trailing slash"
        )
    if any(x in (".", "..") for x in value.split("/")):
        raise ValueError("dot segments are unsupported")
    return value


async def rehearse(data, factory=None):
    if not isinstance(data, dict) or set(data) - {
        "public_origin",
        "prefix",
        "scenarios",
        "probes",
    }:
        raise ValueError(
            "expected public_origin, prefix, scenarios and optional probes"
        )
    origin = data.get("public_origin")
    u = urlsplit(origin) if isinstance(origin, str) else None
    if (
        not u
        or u.scheme not in ("http", "https")
        or not u.hostname
        or u.username
        or u.password
        or u.path not in ("", "/")
        or u.query
        or u.fragment
    ):
        raise ValueError(
            "public_origin must be an HTTP(S) origin without credentials/path/query"
        )
    origin = origin.rstrip("/")
    external = prefix(data.get("prefix", ""))
    scenarios = data.get("scenarios")
    probes = data.get("probes", ["/items", "/docs", "/openapi.json"])
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 20:
        raise ValueError("provide 1..20 scenarios")
    if (
        not isinstance(probes, list)
        or not 1 <= len(probes) <= 20
        or not all(
            isinstance(x, str)
            and x.startswith("/")
            and not x.startswith("//")
            and not any(c in x for c in ("?", "#", "\\", "%"))
            for x in probes
        )
    ):
        raise ValueError("provide 1..20 plain local probe paths")
    results = []
    for cfg in scenarios:
        if not isinstance(cfg, dict) or set(cfg) - {
            "name",
            "root_path",
            "strip_prefix",
            "trust_forwarded",
            "upstream_origin",
        }:
            raise ValueError("unsupported scenario fields")
        if not isinstance(cfg.get("name"), str) or not cfg["name"]:
            raise ValueError("scenario needs a name")
        root = prefix(cfg.get("root_path", ""))
        strip = cfg.get("strip_prefix", True)
        trust = cfg.get("trust_forwarded", True)
        upstream = cfg.get("upstream_origin", "http://upstream.invalid")
        bu = urlsplit(upstream) if isinstance(upstream, str) else None
        if (
            not bu
            or bu.scheme not in ("http", "https")
            or not bu.hostname
            or bu.username
            or bu.password
            or bu.path not in ("", "/")
            or bu.query
            or bu.fragment
        ):
            raise ValueError("upstream_origin must be a plain HTTP(S) origin")
        if type(strip) is not bool or type(trust) is not bool:
            raise ValueError("strip_prefix/trust_forwarded must be booleans")
        # A fresh built-in application avoids mutation of cached OpenAPI servers between scenarios.
        current = demo_app() if factory is None else factory()
        if not callable(current):
            raise TypeError("factory must return an ASGI callable")

        async def proxy(
            scope,
            receive,
            send,
            current=current,
            root=root,
            strip=strip,
            trust=trust,
            bu=bu,
        ):
            scope = dict(scope)
            path = scope["path"]
            if external and not (path == external or path.startswith(external + "/")):
                await send(
                    {"type": "http.response.start", "status": 404, "headers": []}
                )
                await send(
                    {"type": "http.response.body", "body": b"outside public prefix"}
                )
                return
            if strip and external:
                path = path[len(external) :] or "/"
            # Model Uvicorn's full ASGI path, including its configured root path.
            scope["path"] = root + path
            scope["raw_path"] = (root + path).encode("utf-8")
            scope["root_path"] = root
            effective = u if trust else bu
            scope["scheme"] = effective.scheme
            scope["server"] = (
                effective.hostname,
                effective.port or (443 if effective.scheme == "https" else 80),
            )
            scope["headers"] = [
                (k, v) for k, v in scope["headers"] if k.lower() != b"host"
            ] + [(b"host", effective.netloc.encode())]
            await current(scope, receive, send)

        findings = []
        responses = []
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=proxy),
            base_url=origin,
            follow_redirects=False,
            timeout=5,
        ) as client:

            async def request(path):
                try:
                    return await asyncio.wait_for(
                        client.get(path), PROBE_TIMEOUT_SECONDS
                    )
                except TimeoutError as exc:
                    raise ValueError("local ASGI probe exceeded time limit") from exc

            for probe in probes:
                path = external + probe
                response = await request(path)
                item = {"path": path, "status": response.status_code}
                if response.status_code >= 400:
                    findings.append(
                        {
                            "path": path,
                            "kind": "http_error",
                            "status": response.status_code,
                        }
                    )
                if "location" in response.headers:
                    location = urljoin(origin + path, response.headers["location"])
                    target = urlsplit(location)
                    item["location"] = location
                    if (target.scheme, target.netloc) != (u.scheme, u.netloc) or (
                        external
                        and not (
                            target.path == external
                            or target.path.startswith(external + "/")
                        )
                    ):
                        findings.append(
                            {
                                "path": path,
                                "kind": "redirect_escapes_public_base",
                                "target": location,
                            }
                        )
                    # Follow through the same local ASGI proxy only, without external networking.
                    if (target.scheme, target.netloc) == (u.scheme, u.netloc):
                        followed = await request(target.path)
                        item["redirect_target_status"] = followed.status_code
                        if followed.status_code >= 400:
                            findings.append(
                                {
                                    "path": path,
                                    "kind": "redirect_target_error",
                                    "status": followed.status_code,
                                }
                            )
                if "text/html" in response.headers.get("content-type", ""):
                    match = re.search(r"url:\s*(['\"])([^'\"]+)\1", response.text)
                    if match:
                        schema_url = urljoin(origin + path, match.group(2))
                        target = urlsplit(schema_url)
                        item["docs_schema_url"] = schema_url
                        if (target.scheme, target.netloc) != (u.scheme, u.netloc):
                            findings.append(
                                {
                                    "path": path,
                                    "kind": "docs_schema_external",
                                    "target": schema_url,
                                }
                            )
                        else:
                            sr = await request(target.path)
                            item["docs_schema_status"] = sr.status_code
                            if sr.status_code != 200:
                                findings.append(
                                    {
                                        "path": path,
                                        "kind": "docs_schema_unreachable",
                                        "target": schema_url,
                                        "status": sr.status_code,
                                    }
                                )
                if probe.endswith("openapi.json") and response.status_code == 200:
                    try:
                        schema = response.json()
                    except ValueError:
                        raise ValueError("schema response is not JSON")
                    if not isinstance(schema, dict):
                        raise ValueError("schema response must be an object")
                    servers = [
                        x.get("url")
                        for x in schema.get("servers", [])
                        if isinstance(x, dict)
                    ]
                    item["openapi_servers"] = servers
                    expected = external or "/"
                    if (
                        external
                        and expected not in servers
                        and origin + expected not in servers
                    ):
                        findings.append(
                            {
                                "path": path,
                                "kind": "openapi_public_base_missing",
                                "expected": expected,
                                "servers": servers,
                            }
                        )
                responses.append(item)
        results.append(
            {
                "name": cfg["name"],
                "configuration": cfg,
                "responses": responses,
                "findings": findings,
                "passed": not findings,
            }
        )
    return {
        "schema": "rootpath-rehearsal/v1",
        "public_base": origin + external,
        "scenarios": results,
        "needs_review": any(not r["passed"] for r in results),
        "scope": "In-process ASGI model. No DNS, TLS, sockets, real reverse proxy, lifespan startup or production access.",
    }


def analyze(data):
    return asyncio.run(rehearse(data))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input")
    p.add_argument(
        "--factory",
        help="Local MODULE:FACTORY; imports code and creates a fresh ASGI app per scenario",
    )
    p.add_argument("--html")
    args = p.parse_args(argv)
    try:
        factory = None
        if args.factory:
            module, sep, attr = args.factory.partition(":")
            if not sep or not module or not attr:
                raise ValueError("--factory requires MODULE:ATTRIBUTE")
            factory = getattr(importlib.import_module(module), attr)
            if not callable(factory):
                raise ValueError("application is not callable")
        result = asyncio.run(rehearse(load(args.input), factory))
        if args.html:
            write_html(result, args.html)
        print(json.dumps(result, sort_keys=True))
        return int(result["needs_review"])
    except (
        ValueError,
        OSError,
        TypeError,
        ImportError,
        AttributeError,
        httpx.HTTPError,
    ) as e:
        print(str(e), file=sys.stderr)
        return 2


def load(path):
    p = Path(path)
    if p.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("input exceeds 4 MiB")

    def pairs(items):
        d = {}
        for k, v in items:
            if k in d:
                raise ValueError("duplicate JSON key: " + k)
            d[k] = v
        return d

    return json.loads(
        p.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite number")),
    )


def write_html(report, path):
    """Render escaped, searchable evidence tables without external assets."""
    esc = lambda x: html.escape(str(x))

    def table(headers, rows):
        return (
            "<table><thead><tr>"
            + "".join("<th>" + esc(x) + "</th>" for x in headers)
            + "</tr></thead><tbody>"
            + "".join(
                "<tr>" + "".join("<td>" + esc(x) + "</td>" for x in row) + "</tr>"
                for row in rows
            )
            + "</tbody></table>"
        )

    schema = report["schema"]
    sections = []
    cards = []
    if schema == "join-fanout/v1":
        title = "Where the extra join rows come from"
        subtitle = "Polars equi-join rehearsal. Group counts explain row growth before an expanded join is materialized."
        cards = [
            ("Left rows", report["left_rows"]),
            ("Right rows", report["right_rows"]),
            ("Output rows", report["output_rows"]),
            ("Row budget", report["max_rows"]),
        ]
        sections.append(
            "<h2>Keys contributing the most rows</h2>"
            + table(
                ["Key", "Left", "Right", "Matched pairs", "Output"],
                [
                    (
                        json.dumps(x["key"]),
                        x["left_rows"],
                        x["right_rows"],
                        x["matched_pairs"],
                        x["output_rows"],
                    )
                    for x in report["top_keys"]
                ],
            )
        )
        state = "Over row budget" if report["over_budget"] else "Within row budget"
    elif schema == "group-split-audit/v1":
        title = "Cross-validation split review"
        subtitle = "Review observable group, duplicate and time-window overlap before interpreting a validation score."
        cards = [
            ("Observations", report["rows"]),
            ("Folds", len(report["folds"])),
            ("Folds to review", sum(f["needs_review"] for f in report["folds"])),
        ]
        sections.append(
            "<h2>Fold findings</h2>"
            + table(
                [
                    "Fold",
                    "Train / test",
                    "Shared groups",
                    "Shared fingerprints",
                    "Window pairs",
                    "Unseen labels",
                ],
                [
                    (
                        f["fold"],
                        str(f["train_rows"]) + " / " + str(f["test_rows"]),
                        ", ".join(f["shared_groups"]) or "None",
                        ", ".join(f["shared_fingerprints"]) or "None",
                        f["overlapping_window_pairs"],
                        ", ".join(f["test_labels_absent_from_train"]) or "None",
                    )
                    for f in report["folds"]
                ],
            )
        )
        state = (
            "Review findings" if report["needs_review"] else "No declared overlap found"
        )
    elif schema == "compose-readiness-replay/v1":
        title = "What blocked startup"
        subtitle = "One ordered startup attempt, replayed against declared Compose dependency barriers."
        cards = [
            ("Events", len(report["timeline"])),
            ("Early starts", len(report["violations"])),
            ("Not started", len(report["not_started"])),
        ]
        sections.append(
            "<h2>Starts before their barriers were met</h2>"
            + table(
                ["Tick", "Service", "Waiting for"],
                [
                    (x["at"], x["service"], json.dumps(x["blocked_by"]))
                    for x in report["violations"]
                ],
            )
        )
        sections.append(
            "<h2>Observed event timeline</h2>"
            + table(
                ["Tick", "Service", "Event", "Ready to start after event"],
                [
                    (
                        x["at"],
                        x["service"],
                        x["event"],
                        ", ".join(x["ready_to_start"]) or "None",
                    )
                    for x in report["timeline"]
                ],
            )
        )
        state = (
            "Review findings"
            if report["needs_review"]
            else "Observed barriers respected"
        )
    elif schema == "n8n-relocation/v1":
        title = "Workflow relocation review"
        subtitle = "Local export reference mappings only. No server access, credential payloads or workflow activation."
        cards = [
            ("Planned mappings", len(report["operations"])),
            ("Unresolved references", len(report["unresolved"])),
        ]
        sections.append(
            "<h2>Reference changes</h2>"
            + table(
                ["Node", "Reference", "Before", "After"],
                [
                    (
                        x["node_id"],
                        x["kind"],
                        json.dumps(x["before"]),
                        json.dumps(x["after"]),
                    )
                    for x in report["operations"]
                ],
            )
        )
        sections.append(
            "<h2>Unresolved references</h2>"
            + table(
                ["Node", "Kind", "Reason"],
                [(x["node_id"], x["kind"], x["reason"]) for x in report["unresolved"]],
            )
        )
        state = (
            "Ready for review and local application"
            if report["ready"]
            else "Mapping is incomplete"
        )
    else:
        title = "Proxy wiring rehearsal"
        subtitle = "Local ASGI probes compare public redirects, documentation URLs and OpenAPI server prefixes."
        cards = [
            ("Scenarios", len(report["scenarios"])),
            ("Passing scenarios", sum(x["passed"] for x in report["scenarios"])),
        ]
        for scenario in report["scenarios"]:
            sections.append(
                "<h2>"
                + esc(scenario["name"])
                + (" · Pass" if scenario["passed"] else " · Review")
                + "</h2>"
                + table(
                    ["Public path", "Status", "Redirect / schema URL"],
                    [
                        (
                            x["path"],
                            x["status"],
                            x.get("location", x.get("docs_schema_url", "")),
                        )
                        for x in scenario["responses"]
                    ],
                )
            )
            sections.append(
                table(
                    ["Finding", "Path", "Evidence"],
                    [
                        (x["kind"], x["path"], json.dumps(x))
                        for x in scenario["findings"]
                    ],
                )
            )
        state = (
            "Review scenario differences"
            if report["needs_review"]
            else "All probe contracts passed"
        )
    body = html.escape(json.dumps(report, indent=2, ensure_ascii=False))
    css = "body{font:16px/1.6 system-ui;background:#f3f6fa;color:#182438;max-width:1100px;margin:40px auto;padding:0 24px}header{border-bottom:3px solid #137a68;padding-bottom:24px}h1{font-size:2.25rem;line-height:1.15;max-width:800px}h2{margin-top:40px;font-size:1.2rem}.cards{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}.card{background:white;padding:16px 22px;border:1px solid #d2dae5;border-radius:10px;min-width:140px}.card b{display:block;font-size:1.7rem;color:#0b6555}table{border-collapse:collapse;width:100%;background:white;margin-bottom:22px;display:block;overflow:auto}th,td{text-align:left;padding:12px;border-bottom:1px solid #d6deea;vertical-align:top}th{background:#e3eaf2}td{overflow-wrap:anywhere}input{font:inherit;padding:10px;width:min(90%,600px);border:1px solid #8593a6;border-radius:6px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:20px;border:1px solid #d2dae5}.status{font-weight:700;color:#0b6555}footer{margin-top:40px;color:#4a5b73}details{margin-top:30px}label{display:block}"
    card_html = (
        '<div class="cards">'
        + "".join(
            '<div class="card">' + esc(k) + "<b>" + esc(v) + "</b></div>"
            for k, v in cards
        )
        + "</div>"
    )
    page = (
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'
        + esc(title)
        + "</title><style>"
        + css
        + "</style><header><p>LOCAL DIAGNOSTICS · SYNTHETIC EXAMPLE WHEN USING THE BUNDLED FIXTURE</p><h1>"
        + esc(title)
        + "</h1><p>"
        + esc(subtitle)
        + '</p><p class="status">'
        + esc(state)
        + "</p></header>"
        + card_html
        + '<label>Filter evidence rows <input id="q" type="search" placeholder="Service, key, group, path or finding"></label>'
        + "".join(sections)
        + "<details><summary>Complete JSON evidence</summary><pre>"
        + body
        + '</pre></details><footer>Read the repository limitations before acting. These results describe supplied inputs; they do not certify a live system.</footer><script>document.querySelector("#q").addEventListener("input",e=>{const q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))});</script></html>'
    )
    Path(path).write_text(page, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

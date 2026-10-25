# Rootpath Rehearsal

An endpoint can work while redirects point at an internal host or the documentation requests an unreachable OpenAPI schema.

Replay public-path probes through a local ASGI proxy model and compare redirect targets, docs schema URLs and OpenAPI server prefixes across configurations.

## Try the example

Python 3.11+ on Linux. No account or remote service is needed.

```sh
git clone https://github.com/nripankadas07/rootpath-rehearsal.git
cd rootpath-rehearsal
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade "pip>=26.2" "setuptools>=84.1"
python -m pip install .
rootpath-rehearsal example.json --html report.html
```

The correct invented /edge scenario passes. Omitting root_path breaks docs/public redirects; rejecting forwarded-origin information exposes an internal-origin redirect.

The JSON goes to stdout; open `report.html` in a browser for searchable evidence
tables. The bundled [HTML report](demo.html) and [expected JSON](example-output.json)
come from [example.json](example.json), which uses invented data.

Exit 0 means a completed report without the tool's documented review findings;
exit 1 means findings require review; exit 2 means invalid input or an operational
error, with stderr and no partial JSON report. Some bundled examples intentionally
exit 1 to demonstrate a failure diagnosis. Do not discard those findings.


For your own safe local test application, provide a zero-argument factory:

```sh
rootpath-rehearsal example.json --factory your_test_module:make_app
```

This imports and runs your code. The factory must create a fresh ASGI app.
Run with test fixtures, not handlers connected to production systems.

## Input and supported behavior

Supply an HTTP(S) `public_origin` without credentials, a plain `prefix`, a scenarios array and optional local `probes`. Each scenario names root_path, strip_prefix, trust_forwarded and optional upstream_origin. Defaults use the bundled invented FastAPI app. `--factory MODULE:FUNCTION` imports your own local code and creates a fresh ASGI application per scenario.

## Limits and compatibility

4 MiB JSON; 1..20 scenarios and 1..20 probes; each local probe has a five-second deadline. Plain paths only. No sockets, DNS, TLS, actual proxy, WebSockets, authentication, lifespan startup or production access are tested. Factory imports and GET handlers execute your code; use a safe test application and isolated fixtures. Forwarding trust here is a simulation setting, not advice to trust arbitrary headers on a deployed server.

FastAPI 0.162.0 and HTTPX 0.28.1. The scope model follows Uvicorn full-path construction in https://github.com/Kludex/uvicorn/blob/main/uvicorn/protocols/http/h11_impl.py

Pinned FastAPI and HTTPX dependencies. Recheck ASGI server root_path construction and Starlette redirect behavior on upgrades. No claim of end-to-end TLS or network compatibility.

## Verify

```sh
python -m unittest -v
python -m compileall -q .
python -m pip wheel --no-deps -w dist .
python -m venv /tmp/rootpath-rehearsal-check
/tmp/rootpath-rehearsal-check/bin/python -m pip install dist/*.whl
/tmp/rootpath-rehearsal-check/bin/python verify_installed.py
```

The installed check executes the real console command from a temporary working
directory and checks malformed-input exit behavior. CI repeats tests and clean
installation on Python 3.11/3.13, then runs a vulnerability audit. See
[validation coverage](VALIDATION.md) for tested behavior and remaining limits.

## Why this project

Existing http-range-witness and cookie-scope-witness explain protocol semantics; api-mocker supplies mocks. This tool executes ASGI URL wiring contracts against a real FastAPI application.

FastAPI documents the configuration, Uvicorn serves ASGI applications and HTTPX provides a transport. This project assembles a repeatable public-URL contract with specific diagnoses. It is a local model, not a replacement for a real proxy deployment test.

[Research and alternatives](RESEARCH.md) records dated sources, stars, licenses,
maintenance observations and demand limits. No adoption or performance advantage
is claimed. Original code and invented fixtures, developed with AI assistance.
No affiliation with or endorsement by the upstream project is implied.

[License](LICENSE) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Brief](BRIEF.json)

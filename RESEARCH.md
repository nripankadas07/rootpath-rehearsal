# Research and alternatives

Observed on 25 October 2026; repository metadata snapshot at 06:05 UTC, with narrower
comparison searches and README reads later in the same review. Exact receipts
are retained in the portfolio ledger. Searches request GitHub star ordering;
topic/keyword coverage is limited and does not establish a global ranking.

Queries: `api framework stars:>10000 archived:false sort:stars; fastapi proxy test sort:stars`.

| Repository | Observed stars | Last push observed UTC | API license classification |
| --- | ---: | --- | --- |
| [fastapi/fastapi](https://github.com/fastapi/fastapi) | 104104 | 2026-10-23T23:46:14Z | MIT |
| [encode/httpx](https://github.com/encode/httpx) | 15747 | 2026-10-02T12:53:43Z | BSD-3-Clause |
| [Kludex/uvicorn](https://github.com/Kludex/uvicorn) | 11035 | 2026-10-24T21:52:44Z | BSD-3-Clause |

The highest-star relevant comparable found among these is recorded in the table.
Stars indicate an audience to investigate, not user demand or technical quality.
NOASSERTION/unclassified licenses require separate review before reusing code.
These comparables were read as evidence; no competitor code/prose was reused.

## User and evidence

FastAPI developers serving applications beneath a reverse-proxy prefix. An endpoint can work while redirects point at an internal host or the documentation requests an unreachable OpenAPI schema.

- https://github.com/fastapi/fastapi/blob/master/docs/en/docs/advanced/behind-a-proxy.md
- https://github.com/fastapi/fastapi/issues/829

The current official proxy guide describes the concrete redirect and stripped-prefix problems. Issue 829 is historical and closed; this tool does not claim the framework still has that bug. A reusable multi-scenario rehearsal is an inferred need.

## Workflow comparison

FastAPI documents the configuration, Uvicorn serves ASGI applications and HTTPX provides a transport. This project assembles a repeatable public-URL contract with specific diagnoses. It is a local model, not a replacement for a real proxy deployment test.

Our first useful result is the bundled install-and-report example. The other
projects have their own setup, examples and support channels; their installation
times were not benchmarked here. No speed, memory, reliability or feature-absence
superiority claim follows from our successful example. Their broader workflows
may be more appropriate for larger or different tasks.

## Scope and portfolio comparison

Existing http-range-witness and cookie-scope-witness explain protocol semantics; api-mocker supplies mocks. This tool executes ASGI URL wiring contracts against a real FastAPI application.

The five selected projects address separate tasks: join cardinality, fold leakage,
ASGI URL wiring, container startup history and workflow export relocation. They
are not forks or subdivisions of one application. A portfolio-wide inventory of
218 repositories was compared before selection. Reusable packaging/report
boilerplate does not count as the original capability.

Pinned FastAPI and HTTPX dependencies. Recheck ASGI server root_path construction and Starlette redirect behavior on upgrades. No claim of end-to-end TLS or network compatibility.

Discovery path: A three-scenario HTML comparison showing working versus broken /edge routes, plus a factory example for local applications.

Candidate rank 3 of 5 reflects practical usefulness, problem evidence,
distinctness, demonstrability and maintenance burden. It is a judgment, not a
measured score or a prediction of attention. Playwright/browser-agent ideas were
set aside because the existing portfolio already has tracing/replay tools.
Generic top-star lists/tutorial collections were not selected as product anchors.
Polars is used for a Polars-native workflow even though pandas has more stars;
scikit-learn fits the selected evaluation task rather than larger general ML repos.

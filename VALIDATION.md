# Validation coverage

Local Linux/Python 3.12 validation includes core unit/integration cases, real
ecosystem APIs where used, runnable invented example, wheel build and clean
installed console-command checks outside the source tree. The original failure
expectations are preserved while implementation defects are corrected.

## Acceptance checks

- Correct wiring reaches the docs schema and preserves HTTPS /edge redirect targets.
- Wrong root path and forwarded-origin scenarios produce specific findings.
- A supplied local factory receives requests without external network access.
- Scenario app instances do not share an OpenAPI cache.

CI must pass on the intended public default-branch commit before this project is
counted as a verified launch. Public repository existence alone is insufficient.
Remote CI links and commit receipts belong in the portfolio ledger; this text
does not claim an unobserved run passed.

Windows/macOS, production data and live external service operation are untested.
4 MiB JSON; 1..20 scenarios and 1..20 probes; each local probe has a five-second deadline. Plain paths only. No sockets, DNS, TLS, actual proxy, WebSockets, authentication, lifespan startup or production access are tested. Factory imports and GET handlers execute your code; use a safe test application and isolated fixtures. Forwarding trust here is a simulation setting, not advice to trust arbitrary headers on a deployed server.

The cloud browser rejects local file URLs, so the generated HTML report was
checked structurally and for escaped output but was not visually inspected in
that browser. Console behavior and installed commands are independently tested.

The initial new-project environment audit flagged its preinstalled pip 25.0.1.
The installer is upgraded to pip 26.2+ before dependency installation and the
full environment audit is rerun. Project runtime dependencies were not the
source of those installer advisories. No advisory is suppressed.

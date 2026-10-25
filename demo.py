import json
from pathlib import Path

from rootpath_rehearsal import analyze, write_html

base = Path(__file__).parent
r = analyze(json.loads((base / "example.json").read_text()))
(base / "example-output.json").write_text(
    json.dumps(r, indent=2, sort_keys=True) + "\n"
)
write_html(r, base / "demo.html")
print(json.dumps(r, indent=2, sort_keys=True))

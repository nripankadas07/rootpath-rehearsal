import json
import pathlib
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    data = pathlib.Path(__file__).with_name("example.json").read_bytes()
    sample = pathlib.Path(tmp) / "example.json"
    sample.write_bytes(data)
    r = subprocess.run(
        [
            str(pathlib.Path(sys.executable).with_name("rootpath-rehearsal")),
            str(sample),
        ],
        check=False,
        cwd=tmp,
        text=True,
        capture_output=True,
    )
    assert r.returncode in (0, 1), (r.returncode, r.stderr)
    report = json.loads(r.stdout)
    assert isinstance(report, dict) and "schema" in report
    bad = pathlib.Path(tmp) / "bad.json"
    bad.write_text('{"bad": true}')
    r = subprocess.run(
        [str(pathlib.Path(sys.executable).with_name("rootpath-rehearsal")), str(bad)],
        check=False,
        cwd=tmp,
        text=True,
        capture_output=True,
    )
    assert r.returncode == 2 and not r.stdout, (r.returncode, r.stdout, r.stderr)
print("Installed CLI and malformed-input behavior pass outside source tree")

"""Check that the precise checksum exception still rejects synthetic credentials."""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def verify(binary: Path, root: Path) -> None:
    relative = Path("tools/container_runtime_review.json")
    digest = hashlib.sha256((root / "backend/opennotelm/secrets.py").read_bytes()).hexdigest()
    record = f'  "backend/opennotelm/secrets.py": "{digest}",\n'
    # The production digest must itself be covered. An unreviewed source change fails closed.
    cases = [
        (relative, record, False),
        (Path("other.json"), record, True),
        (relative, record.replace(digest, hashlib.sha256(b"synthetic-other").hexdigest()), True),
        (relative, 'api_key = "' + hashlib.sha256(b"synthetic-key").hexdigest() + '"\n', True),
    ]
    with tempfile.TemporaryDirectory(prefix="opennotelm-secret-contract-") as temp:
        for index, (filename, text, rejected) in enumerate(cases):
            directory = Path(temp) / str(index)
            target = directory / filename
            target.parent.mkdir(parents=True)
            target.write_text(text)
            report = Path(temp) / f"report-{index}.json"
            result = subprocess.run(
                [
                    str(binary),
                    "dir",
                    str(directory),
                    "--config",
                    str(root / ".gitleaks.toml"),
                    "--redact=100",
                    "--report-format",
                    "json",
                    "--report-path",
                    str(report),
                ],
                capture_output=True,
            )
            if result.returncode != int(rejected):
                raise RuntimeError(f"Secret scan contract failed for synthetic case {index + 1}")
            findings = json.loads(report.read_text())
            if bool(findings) != rejected:
                raise RuntimeError("Secret scan report does not match rejection")
    print("Secret-scanner checksum exception and three rejection cases passed.")


if __name__ == "__main__":
    verify(Path(sys.argv[1]).resolve(), Path(__file__).resolve().parent.parent)

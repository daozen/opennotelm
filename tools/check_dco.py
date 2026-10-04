"""Check new PR commits for a matching author DCO footer without logging messages."""

import os
import re
import subprocess


def main() -> None:
    base, head = os.environ["DCO_BASE"], os.environ["DCO_HEAD"]
    if not all(re.fullmatch(r"[a-f0-9]{40}", value) for value in (base, head)):
        raise SystemExit("Invalid commit boundary")
    commits = subprocess.check_output(["git", "rev-list", f"{base}..{head}"], text=True)
    failures = []
    for commit in commits.splitlines():
        record = subprocess.check_output(
            ["git", "show", "--no-patch", "--format=%an%n%ae%n%B", commit], text=True
        )
        name, email, message = record.split("\n", 2)
        expected = f"Signed-off-by: {name} <{email}>"
        if expected.casefold() not in {line.strip().casefold() for line in message.splitlines()}:
            failures.append(commit[:12])
    if failures:
        raise SystemExit("Missing author DCO sign-off in commits: " + ", ".join(failures))
    print("New contribution commits have matching DCO sign-offs.")


if __name__ == "__main__":
    main()

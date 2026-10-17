"""Check local Markdown file links in the public tree, without network access."""
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = {"data", ".test-output", ".venv", "__pycache__", ".git"}


def check(root=ROOT):
    files = sorted([*root.glob("*.md"), *(root / "docs").rglob("*.md"),
                    *(root / "examples").rglob("*.md")])
    errors, checked = [], 0
    for file in files:
        text = re.sub(r"(?ms)^```.*?^```[^\n]*", "", file.read_text(encoding="utf-8"))
        text = re.sub(r"`[^`\n]+`", "", text)
        for match in re.finditer(r"!?\[[^\]\n]*\]\(([^)\n]+)\)", text):
            target = match[1].strip()
            target = target[1:target.index(">")] if target.startswith("<") else target.split(' "', 1)[0]
            if re.match(r"^[A-Za-z]:[\\/]", target) or target.startswith(("/", "\\")):
                errors.append(f"{file.relative_to(root)}: absolute local link: {target}")
                continue
            parsed = urlsplit(target)
            if parsed.scheme or not parsed.path:
                continue
            checked += 1
            path = (file.parent / unquote(parsed.path)).resolve()
            if not path.is_relative_to(root):
                errors.append(f"{file.relative_to(root)}: link leaves public tree: {target}")
                continue
            relative = path.relative_to(root)
            if (any(part in PRIVATE for part in relative.parts)
                    or (path.name.startswith(".env") and path.name != ".env.example")):
                errors.append(f"{file.relative_to(root)}: link targets private/generated data: {target}")
            elif not path.exists():
                errors.append(f"{file.relative_to(root)}: missing link target: {target}")
    return checked, errors


if __name__ == "__main__":
    count, problems = check()
    for problem in problems:
        print(problem)
    print(f"Checked {count} local Markdown links; {len(problems)} errors. External URLs/anchors are not checked.")
    sys.exit(bool(problems))

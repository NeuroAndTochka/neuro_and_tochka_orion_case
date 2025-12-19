#!/usr/bin/env python3
from pathlib import Path

def load_names_from_log(path: Path) -> tuple[list[str], set[str]]:
    """Read line-separated names from a.log."""
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    return lines, set(lines)

def collect_disk_names(doc_root: Path) -> set[str]:
    return {p.name for p in doc_root.rglob("*") if p.is_file()}

def collect_extras(doc_root: Path, names: set[str]) -> dict[str, list[str]]:
    extras: dict[str, list[str]] = {}
    for file_path in doc_root.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.name in names:
            continue
        rel = file_path.relative_to(doc_root)
        folder = rel.parts[0] if rel.parts else "."
        extras.setdefault(folder, []).append(rel.as_posix())
    for folder in extras:
        extras[folder].sort()
    return extras

def main() -> None:
    all_lines, names = load_names_from_log(Path("a.log"))
    doc_root = Path("documents")
    disk_names = collect_disk_names(doc_root)
    extras = collect_extras(doc_root, names)

    print(f"lines in a.log: {len(all_lines)}")
    print(f"unique names   : {len(names)}")
    print(f"duplicates     : {len(all_lines) - len(names)}")
    missing_on_disk = sorted(names - disk_names)
    if missing_on_disk:
        print("\nIn a.log but not found on disk:")
        for name in missing_on_disk:
            print(f"  {name}")
        print(f"  total: {len(missing_on_disk)}\n")

    for folder in sorted(extras):
        files = extras[folder]
        if not files:
            continue
        print(folder)
        for fp in files:
            print(f"  {fp}")
        print(f"  total: {len(files)}\n")

if __name__ == "__main__":
    main()

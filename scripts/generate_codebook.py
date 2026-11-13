"""Regenerate the public codebook after editing static/survey.json."""

import csv
import io
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
book_path = ROOT / "static/codebook.json"

schema = json.loads(
    (ROOT / "static/survey.json").read_text(encoding="utf-8-sig")
)
book = json.loads(
    book_path.read_text(encoding="utf-8-sig")
)

book.update(
    version=schema["version"],
    sections=schema["sections"],
)

output = io.StringIO()
writer = csv.writer(output, lineterminator="\n")

writer.writerow([
    "version",
    "instrument",
    "part",
    "id",
    "question",
    "type",
    "options",
    "fields_or_columns",
    "notes",
])

for key, label in book["metadata"].items():
    writer.writerow([
        schema["version"],
        "all",
        "metadata",
        key,
        label,
        "metadata",
        "",
        "",
        "",
    ])

for section in schema["sections"]:
    for question in section["questions"]:
        writer.writerow([
            schema["version"],
            section["instrument"],
            section["id"],
            question["id"],
            question["label"],
            question["type"],
            json.dumps(
                question.get("options", []),
                ensure_ascii=False,
            ),
            json.dumps(
                question.get("fields", question.get("columns", [])),
                ensure_ascii=False,
            ),
            question.get("help", ""),
        ])

expected = {
    book_path: json.dumps(book, ensure_ascii=False, indent=2),
    ROOT / "static/codebook.csv": "\ufeff" + output.getvalue(),
}

if "--check" in sys.argv:
    mismatches = [
        str(path.relative_to(ROOT))
        for path, content in expected.items()
        if path.read_bytes().replace(b"\r\n", b"\n")
        != content.encode("utf-8").replace(b"\r\n", b"\n")
    ]

    if mismatches:
        raise SystemExit(
            "Codebook is stale: "
            + ", ".join(mismatches)
            + ". Run python scripts/generate_codebook.py."
        )

    print("Codebook matches questionnaire.")

else:
    for path, content in expected.items():
        path.write_bytes(content.encode("utf-8"))

    print("Codebook regenerated.")  
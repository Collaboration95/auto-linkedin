#!/usr/bin/env python3
"""Export application records for the static, double-clickable run log."""

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from config import select_workspace, configuration, local_now
from zoneinfo import ZoneInfo

ROOT = select_workspace()



def write_json(path, value):
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".export-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(value)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def local_file(root, relative):
    if not relative:
        return None
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        return None
    return path


def export_dashboard(root=ROOT):
    root = root.resolve()
    applications = []
    for source in sorted((root / "applications/records").glob("*/record.json")):
        record = json.loads(source.read_text())
        def resume(saved):
            path = local_file(root, saved.get("exact_resume_copy"))
            return {"id": saved.get("id"), "file": path.name if path else None,
                    "url": "../" + path.relative_to(root).as_posix() if path else None}
        events = [{"at": e.get("at"), "status": e.get("status"), "note": e.get("note", "")}
                  for e in record.get("events", [])]
        submissions = [{"at": s.get("submitted_at"), "resume": resume(s),
                        "applied_by": s.get("applied_by") or record.get("applied_by")}
                       for s in record.get("submissions", [])]
        prepared = record.get("prepared")
        description = local_file(root, record.get("job_description_path"))
        applications.append({"id": record["application_id"], "company": record["company"],
            "title": record["role"], "location": record.get("location", ""),
            "status": record["status"], "applied_by": record.get("applied_by"),
            "job_url": record.get("canonical_listing_url") or record.get("listing_url"),
            "application_url": record.get("application_url"),
            "captured_at": record.get("captured_at"), "updated_at": record.get("status_updated_at"),
            "description": description.read_text() if description else "",
            "notes": record.get("notes", ""), "events": events, "submissions": submissions,
            "record_url": "../" + source.relative_to(root).as_posix(),
            "blocked_on_answer_ids": record.get("blocked_on_answer_ids", []),
            "prepared": {"at": prepared.get("prepared_at"), "resume": resume(prepared)} if prepared else None})
    applications.sort(key=lambda app: app.get("updated_at") or "", reverse=True)
    tz = configuration(root)["timezone"]
    generated_at = local_now(root).isoformat()
    from questions import inbox
    from answers import store
    payload = {"questions": inbox(root, local_now(root)), "answer_revision": store(root).get("revision", 0), "answer_import_ids": sorted(store(root).get("imports", {})), "timezone": tz, "generated_at": generated_at, "applications": applications}
    assets = Path(__file__).resolve().parents[1] / "dashboard"
    (root / "dashboard").mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "app.js", "style.css", "runs.js", "questions.js"):
        source = assets / name
        destination = root / "dashboard" / name
        if source.resolve() != destination.resolve():
            shutil.copyfile(source, destination)
    directory = root / "dashboard/data"
    write_json(directory / "applications.json", payload)
    # Classic script works from file://; browsers commonly block fetch() of local JSON.
    write_text(root / "dashboard/data.js", "window.JOB_SEARCH_DATA = " + json.dumps(payload, ensure_ascii=True) + ";\n")
    return {"path": str(root / "dashboard/index.html"), "applications": len(applications)}


if __name__ == "__main__":
    print(json.dumps(export_dashboard(), indent=2))

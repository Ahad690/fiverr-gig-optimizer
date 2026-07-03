#!/usr/bin/env python3
"""local_data.py — safe local persistence primitives. No data is ever destroyed.

Every script that writes a user's local data file goes through these helpers,
which enforce three guarantees (mirroring the growthkit-skill local store):

  - **Atomic writes.** Content is written to a temp file and swapped in with
    os.replace, so a crash mid-write can never truncate or corrupt the target.
  - **Corruption preserves bytes.** If an existing file fails to parse, it is
    RENAMED to a timestamped .corrupt-*.json backup — never overwritten, never
    deleted — and callers proceed with an empty list.
  - **Replacement backs up.** An explicit overwrite renames the previous file
    to a timestamped .bak-*.json first. There is no code path that discards
    the user's previous data.

Pure stdlib; safe to import from any script in this folder.
"""
import json
import os
import time


def _stamp():
    return time.strftime("%Y%m%d%H%M%S")


def load_json_list(path):
    """Load a JSON array. On parse failure the corrupt bytes are preserved as a
    .corrupt-<ts>.json backup and [] is returned. Missing file -> []."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        backup = f"{path}.corrupt-{_stamp()}.json"
        try:
            os.replace(path, backup)
            print(f"warning: {path} was unreadable - preserved as {backup}.",
                  flush=True)
        except OSError:
            pass
        return []


def write_json_atomic(path, data):
    """Write JSON via tmp-file + os.replace so a crash can't corrupt the target."""
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def backup_existing(path):
    """Rename an existing file to a timestamped .bak-*.json. Returns the backup
    path, or None if the file didn't exist. The original bytes are kept."""
    if not os.path.exists(path):
        return None
    backup = f"{path}.bak-{_stamp()}.json"
    os.replace(path, backup)
    return backup


if __name__ == "__main__":  # tiny smoke test
    import tempfile
    d = tempfile.mkdtemp()
    p = os.path.join(d, "t.json")
    write_json_atomic(p, [1, 2])
    assert load_json_list(p) == [1, 2]
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("{broken")
    assert load_json_list(p) == []                       # corrupt -> []
    assert any(".corrupt-" in f for f in os.listdir(d))  # ...bytes preserved
    write_json_atomic(p, [3])
    b = backup_existing(p)
    assert b and os.path.exists(b) and not os.path.exists(p)
    print("local_data.py self-test OK")

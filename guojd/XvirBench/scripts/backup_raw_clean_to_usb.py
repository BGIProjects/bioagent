#!/usr/bin/env python3
"""Backup Rawdata / Cleandata under XvirBench/batches to a USB drive.

Mirrors the batches directory tree onto the USB, copies symlink *targets*
(actual FASTQ), and skips files already present under USB data/ (the
FP270013120_L01 files copied earlier) as well as dest files of the same size.

Default layout::

    /data/user/guojindan/Projects/XvirBench/batches/<project>/.../Rawdata
    -> /media/wt02/Elements/XvirBench/batches/<project>/.../Rawdata

If a project has Cleandata, that tree is copied (including nested Rawdata).
Otherwise each Rawdata directory is copied. subsample_50k is skipped unless
``--include-subsample``.

Usage::

    python3 backup_raw_clean_to_usb.py                 # dry-run (default)
    python3 backup_raw_clean_to_usb.py --run           # actually copy
    python3 backup_raw_clean_to_usb.py --run --include-subsample
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

BATCHES = Path("/data/user/guojindan/Projects/XvirBench/batches")
USB_ROOT = Path("/media/wt02/Elements")

DATA_SUFFIXES = (".fq.gz", ".fastq.gz", ".fq", ".fastq")
META_NAMES = {"sampleinfo.tsv", "sampleinfo.txt"}


def is_data_file(name: str) -> bool:
    return name.lower().endswith(DATA_SUFFIXES)


def dir_kind(path: Path):
    n = path.name.lower()
    if n == "cleandata":
        return "Cleandata"
    if n == "rawdata":
        return "Rawdata"
    return None


def under_subsample(path: Path) -> bool:
    return "subsample_50k" in path.parts


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def discover_roots(batches: Path, include_subsample: bool):
    """Cleandata dirs, plus Rawdata dirs that are not nested in a Cleandata."""
    found = []
    for dirpath, dirnames, _filenames in os.walk(batches):
        d = Path(dirpath)
        if d == batches:
            continue
        if not include_subsample and under_subsample(d):
            dirnames[:] = []
            continue
        if dir_kind(d) is None:
            continue
        found.append(d)

    cleandata = [p for p in found if p.name.lower() == "cleandata"]
    rawdata = []
    for p in found:
        if p.name.lower() != "rawdata":
            continue
        if any(is_relative_to(p, c) for c in cleandata):
            continue
        rawdata.append(p)
    return sorted(cleandata + rawdata)


def index_usb_existing(usb_data: Path):
    """basename -> size for files already dumped under USB data/."""
    idx = {}
    if not usb_data.is_dir():
        return idx
    for dirpath, _dirnames, filenames in os.walk(usb_data):
        for fn in filenames:
            if not is_data_file(fn):
                continue
            p = Path(dirpath) / fn
            try:
                idx[fn] = p.stat().st_size
            except OSError:
                continue
    return idx


def iter_source_files(root: Path):
    files = []
    for dirpath, _dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        for fn in filenames:
            if is_data_file(fn) or fn in META_NAMES:
                files.append(d / fn)
    if root.name.lower() == "rawdata":
        for meta in META_NAMES:
            m = root.parent / meta
            if m.is_file():
                files.append(m)
    return files


def disk_free(path: Path) -> int:
    path.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(path).free


def classify_file(src, batches, dest_root, usb_idx):
    """Return (action, bytes). action: copy / skip_usb / skip_dest / missing."""
    if src.is_symlink() and not src.exists():
        return "missing", 0
    if not src.exists():
        return "missing", 0
    size = src.stat().st_size
    real_name = Path(os.path.realpath(src)).name
    if real_name in usb_idx and usb_idx[real_name] == size:
        return "skip_usb", size

    rel = src.relative_to(batches)
    dest = dest_root / rel
    if dest.exists() and dest.is_file():
        try:
            if dest.stat().st_size == size:
                return "skip_dest", size
        except OSError:
            pass
    return "copy", size


def run_rsync(batches, dest_root, rel_paths, dry_run):
    if not rel_paths:
        print("Nothing to copy.")
        return 0
    dest_root.mkdir(parents=True, exist_ok=True)
    list_file = dest_root / "_backup_files_from.txt"
    list_file.write_text("\n".join(rel_paths) + "\n")
    cmd = [
        "rsync",
        "-rLvhP",
        "--inplace",
        "--no-owner",
        "--no-group",
        "--no-perms",
        "--size-only",
        "--info=progress2",
        "--files-from={}".format(list_file),
        "{}/".format(batches),
        "{}/".format(dest_root),
    ]
    if dry_run:
        cmd.insert(1, "-n")
    print("+", " ".join(cmd[:9]), "...  ({} files)".format(len(rel_paths)))
    return subprocess.call(cmd)


def gb(n):
    return "{:.1f}G".format(n / 1e9)


def main():
    # Line-buffer stdout so plan prints before rsync progress.
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--src", type=Path, default=BATCHES, help="batches root")
    ap.add_argument("--usb", type=Path, default=USB_ROOT, help="USB mount root")
    ap.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="override dest root (default: USB/XvirBench/batches)",
    )
    ap.add_argument(
        "--existing-data",
        type=Path,
        default=None,
        help="USB dir of already-copied lane files (default: USB/data)",
    )
    ap.add_argument(
        "--include-subsample",
        action="store_true",
        help="also copy subsample_50k Rawdata",
    )
    ap.add_argument("--run", action="store_true", help="actually copy; default is dry-run")
    args = ap.parse_args()

    batches = args.src.resolve()
    usb = args.usb.resolve()
    dest_root = (args.dest or (usb / "XvirBench" / "batches")).resolve()
    usb_data = (args.existing_data or (usb / "data")).resolve()
    dry_run = not args.run

    if not batches.is_dir():
        print("ERROR: source not found: {}".format(batches), file=sys.stderr)
        return 1
    if not usb.is_dir():
        print("ERROR: USB not mounted: {}".format(usb), file=sys.stderr)
        return 1

    usb_idx = index_usb_existing(usb_data)
    roots = discover_roots(batches, args.include_subsample)

    print("SRC           {}".format(batches))
    print("DEST          {}".format(dest_root))
    print("SKIP USB data {}  ({} files already there)".format(usb_data, len(usb_idx)))
    print("MODE          {}".format("DRY-RUN" if dry_run else "COPY"))
    print("roots         {}".format(len(roots)))
    for r in roots:
        print("  - {}".format(r.relative_to(batches)))
    print()

    counts = {"copy": 0, "skip_usb": 0, "skip_dest": 0, "missing": 0}
    bytes_ = {"copy": 0, "skip_usb": 0, "skip_dest": 0, "missing": 0}
    to_copy = []
    skip_rows = ["relpath\taction\tsize\trealpath"]

    seen = set()
    for root in roots:
        for src in iter_source_files(root):
            key = str(src)
            if key in seen:
                continue
            seen.add(key)
            action, size = classify_file(src, batches, dest_root, usb_idx)
            try:
                rel = src.relative_to(batches)
            except ValueError:
                print("WARN skip outside batches: {}".format(src))
                continue
            counts[action] += 1
            bytes_[action] += size
            skip_rows.append("{}\t{}\t{}\t{}".format(rel, action, size, os.path.realpath(src)))
            if action == "copy":
                to_copy.append(str(rel))

    print("==== plan ====")
    print("  copy       {:5d} files  {}".format(counts["copy"], gb(bytes_["copy"])))
    print("  skip_usb   {:5d} files  {}  (already under {})".format(
        counts["skip_usb"], gb(bytes_["skip_usb"]), usb_data))
    print("  skip_dest  {:5d} files  {}  (same size on dest)".format(
        counts["skip_dest"], gb(bytes_["skip_dest"])))
    print("  missing    {:5d} files  (broken symlink / absent)".format(counts["missing"]))
    free = disk_free(dest_root if dest_root.parent.exists() else usb)
    print("  USB free   {}".format(gb(free)))
    if bytes_["copy"] > free * 0.95:
        print("ERROR: not enough free space on USB.", file=sys.stderr)
        return 2

    dest_root.mkdir(parents=True, exist_ok=True)
    log = dest_root / "_backup_plan.tsv"
    log.write_text("\n".join(skip_rows) + "\n")
    print("  plan TSV   {}".format(log))

    rc = run_rsync(batches, dest_root, to_copy, dry_run=dry_run)
    if rc != 0:
        print("rsync exited {}".format(rc), file=sys.stderr)
        return rc
    if dry_run:
        print("\nDry-run only. Re-run with --run to copy.")
    else:
        print("\nCopy finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Build the /train program zip: the tulip/ folder under a top-level
tulip/ entry, without what a build makes (the top-level runs/ and data/
folders), model files, caches or local DBs. gen/data and tests/data are
program files and stay. Prints the file count, size and sha256. The
entries are sorted and dated 2026-09-27 00:00, so the same tree gives the
same zip.

    python3 make_package.py tulip-package.zip"""
import hashlib
import pathlib
import sys
import zipfile

SRC = pathlib.Path(__file__).resolve().parent.parent / "tulip"
TOP_SKIP = {"runs", "data", "previous", "upload", "uploads"}
SKIP_DIRS = {"__pycache__", ".work", ".git"}
SKIP_SUFFIX = {".pt", ".pyc", ".db", ".tmp", ".log"}


def members():
    for path in sorted(SRC.rglob("*")):
        rel = path.relative_to(SRC)
        dirs = rel.parts[:-1] if path.is_file() else rel.parts
        if (dirs and dirs[0] in TOP_SKIP) or \
                any(part in SKIP_DIRS for part in dirs):
            continue
        if path.is_file() and path.suffix not in SKIP_SUFFIX and \
                not path.name.endswith(".confidence.json"):
            yield path, rel


def main(out):
    out = pathlib.Path(out)
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path, rel in members():
            info = zipfile.ZipInfo(str(pathlib.PurePosixPath("tulip") / rel),
                                   date_time=(2026, 9, 27, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, path.read_bytes())
            n += 1
    data = out.read_bytes()
    print("%s: %d files, %d bytes, sha256 %s" % (
        out.name, n, len(data), hashlib.sha256(data).hexdigest()))


if __name__ == "__main__":
    main(sys.argv[1])

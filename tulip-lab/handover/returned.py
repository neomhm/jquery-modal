"""What the /train page would send back from a finished run: the files the
run made or changed (compared with the unpacked program), of the allowed
kinds, outside hidden folders; at most 60. usage: returned.py <folder>"""
import pathlib
import sys

ALLOWED = {".pt", ".pth", ".safetensors", ".bin", ".ckpt", ".json",
           ".jsonl", ".txt", ".md", ".csv", ".tsv", ".log", ".npy", ".npz",
           ".gguf", ".onnx", ".model", ".vocab", ".yaml", ".yml", ".png",
           ".svg"}
folder = pathlib.Path(sys.argv[1])


def listing(name):
    out = {}
    for line in (folder / name).read_text().splitlines():
        path, mtime = line.rsplit("\t", 1)
        out[path] = float(mtime)
    return out


before, after = listing("before.txt"), listing("after.txt")
made = sorted(p for p, t in after.items() if before.get(p) != t)
hidden = [p for p in made if any(part.startswith(".")
                                 for part in p.split("/")[:-1])]
kinds = [p for p in made if p not in hidden and
         pathlib.PurePosixPath(p).suffix.lower() in ALLOWED]
other = [p for p in made if p not in hidden and p not in kinds]
root = folder / "tulip"
print("made or changed by the run: %d files (%d in hidden folders, not "
      "sent)" % (len(made), len(hidden)))
print("sent back (allowed kinds): %d of at most 60" % len(kinds))
for p in kinds:
    print("  %-48s %10d bytes%s" % (p, (root / p).stat().st_size,
                                     "  (changed)" if p in before else ""))
if other:
    print("not sent (kind not allowed): %s" % ", ".join(other))
sys.exit(0 if len(kinds) <= 60 else 1)

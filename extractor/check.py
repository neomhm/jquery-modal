"""
check.py - look at this machine and say what it can do.

    py check.py

Prints a table and writes runs/env.json with: operating system, Python
and torch versions, CUDA or ROCm, the GPU and its memory, bf16 support,
CPU count, RAM, free disk, package versions, whether Wikipedia can be
reached, and which preset build.py would choose.

It never installs or upgrades anything (build.py installs missing small
packages, but never torch).
"""
import importlib
import json
import os
import pathlib
import platform
import shutil
import sys
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
WIKI_URL = "https://huggingface.co/api/datasets/wikimedia/wikipedia"
PACKAGES = ["torch", "tokenizers", "faker", "phonenumbers", "numpy",
            "datasets", "hijridate"]
REQUIRED = ["torch", "tokenizers", "faker", "phonenumbers", "numpy"]


def ram_gb():
    """Total RAM in GB, without extra libraries."""
    try:
        if hasattr(os, "sysconf") and "SC_PHYS_PAGES" in os.sysconf_names:
            return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9
    except (ValueError, OSError):
        pass
    if sys.platform == "win32":
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        return status.ullTotalPhys / 1e9
    return None


def package_versions():
    found = {}
    for name in PACKAGES:
        try:
            module = importlib.import_module(name)
        except Exception:
            found[name] = None
            continue
        version = getattr(module, "__version__",
                          getattr(module, "VERSION", None))
        if version is None:
            try:
                from importlib import metadata
                version = metadata.version(name)
            except Exception:
                version = "?"
        found[name] = str(version)
    return found


def wikipedia_reachable(timeout=10):
    """Can we reach huggingface.co (where the Wikipedia text lives)?"""
    began = time.time()
    try:
        with urllib.request.urlopen(WIKI_URL, timeout=timeout) as answer:
            ok = answer.status == 200
    except Exception as problem:
        return False, "%s (%.1fs)" % (type(problem).__name__,
                                      time.time() - began)
    return ok, "HTTP 200 (%.1fs)" % (time.time() - began)


def torch_facts():
    facts = {"torch": None, "cuda": False, "backend": "cpu",
             "device_name": None, "device_memory_gb": None,
             "bf16": False, "torch_ok": False}
    try:
        import torch
    except Exception:
        return facts
    facts["torch"] = torch.__version__
    major_minor = tuple(int(x) for x in
                        torch.__version__.split("+")[0].split(".")[:2])
    facts["torch_ok"] = major_minor >= (2, 4)     # nn.RMSNorm needs 2.4
    if torch.cuda.is_available():
        facts["cuda"] = True
        facts["backend"] = "rocm" if getattr(torch.version, "hip", None) \
            else "cuda"
        props = torch.cuda.get_device_properties(0)
        facts["device_name"] = props.name
        facts["device_memory_gb"] = round(props.total_memory / 1e9, 1)
        try:
            facts["bf16"] = bool(torch.cuda.is_bf16_supported())
        except Exception:
            facts["bf16"] = False
    return facts


def choose_preset(facts):
    """build.py with no preset: full when a GPU is present, else pilot."""
    return "full" if facts.get("cuda") else "pilot"


def collect():
    facts = torch_facts()
    wiki_ok, wiki_note = wikipedia_reachable()
    disk = shutil.disk_usage(HERE)
    env = {
        "checked": time.strftime("%Y-%m-%d %H:%M:%S"),
        "os": "%s %s" % (platform.system(), platform.release()),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "torch": facts["torch"],
        "torch_ok": facts["torch_ok"],
        "gpu": facts["cuda"],
        "backend": facts["backend"],
        "device_name": facts["device_name"],
        "device_memory_gb": facts["device_memory_gb"],
        "bf16": facts["bf16"],
        "cpu_count": os.cpu_count(),
        "ram_gb": round(ram_gb() or 0, 1),
        "free_disk_gb": round(disk.free / 1e9, 1),
        "packages": package_versions(),
        "wiki_reachable": wiki_ok,
        "wiki_note": wiki_note,
        "preset": choose_preset(facts),
    }
    missing = [p for p in REQUIRED if not env["packages"].get(p)]
    env["missing_required"] = missing
    return env


def show(env):
    rows = [
        ("Operating system", env["os"] + " / " + env["machine"]),
        ("Python", env["python"]),
        ("torch", "%s%s" % (env["torch"] or "NOT INSTALLED",
                            "" if env["torch_ok"] or not env["torch"]
                            else "  (too old: 2.4 or newer needed)")),
        ("GPU", ("%s, %s GB (%s)" % (env["device_name"],
                                      env["device_memory_gb"],
                                      env["backend"].upper()))
         if env["gpu"] else "none - CPU only"),
        ("bf16", "yes" if env["bf16"] else "no"),
        ("CPUs", str(env["cpu_count"])),
        ("RAM", "%s GB" % env["ram_gb"]),
        ("Free disk", "%s GB" % env["free_disk_gb"]),
        ("Wikipedia", ("reachable - " if env["wiki_reachable"]
                       else "NOT reachable - ") + env["wiki_note"]),
    ]
    for name, version in env["packages"].items():
        rows.append(("  " + name, version or "missing"))
    rows.append(("build.py would choose", env["preset"]))
    width = max(len(r[0]) for r in rows)
    print("-" * 64)
    for name, value in rows:
        print("%-*s  %s" % (width, name, value))
    print("-" * 64)
    if env["missing_required"]:
        print("Missing required packages: %s" % ", ".join(
            env["missing_required"]))
        if "torch" in env["missing_required"]:
            print("torch is never installed by these scripts. Install the")
            print("build that fits your machine (CUDA, ROCm or CPU) first.")
    if env["preset"] == "full" and (env["device_memory_gb"] or 0) < 12:
        print("Note: the full preset wants 12 GB of GPU memory or more.")


def main():
    env = collect()
    show(env)
    out = HERE / "runs" / "env.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(env, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print("written:", out.relative_to(HERE))
    return env


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()

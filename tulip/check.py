"""
check.py - look at this machine and say what it can do.

    py check.py

Prints a table and writes runs/env.json with: operating system, Python
and torch versions, CUDA or ROCm, the GPU and its memory, bf16 support,
CPU count, RAM, free disk, package versions, the MEASURED speed of
matrix products (TFLOPS) on each device, and which preset build.py would
choose. It also warns when a new GPU cannot run with the installed torch.

It never installs or upgrades anything (build.py installs missing small
packages, but never torch: MEGA9 has a ROCm build and the desktop a CUDA
build, and replacing either would break it).
"""
import importlib
import json
import os
import pathlib
import platform
import shutil
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
PACKAGES = ["torch", "tokenizers", "openpyxl", "phonenumbers", "numpy",
            "hijridate"]
REQUIRED = ["torch", "tokenizers", "openpyxl", "phonenumbers", "numpy"]


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


def matmul_tflops(torch, device, dtype, size, seconds=1.0):
    """Multiply two size x size matrices again and again for about
    `seconds` and return the speed in TFLOPS (2 * size^3 operations per
    product). None when this device cannot do it."""
    try:
        a = torch.randn(size, size, device=device, dtype=dtype)
        b = torch.randn(size, size, device=device, dtype=dtype)
        for _ in range(2):                       # warm-up
            (a @ b).sum().item()
        done, began = 0, time.time()
        while time.time() - began < seconds or done < 3:
            c = a @ b
            done += 1
        c.sum().item()                           # wait for the device
        elapsed = time.time() - began
        return round(2 * size ** 3 * done / elapsed / 1e12, 3)
    except Exception:
        return None


def torch_facts():
    facts = {"torch": None, "cuda": False, "backend": "cpu",
             "device_name": None, "device_memory_gb": None,
             "compute_capability": None, "bf16": False, "torch_ok": False,
             "tflops": {}, "warnings": []}
    try:
        import torch
    except Exception:
        return facts
    facts["torch"] = torch.__version__
    major_minor = tuple(int(x) for x in
                        torch.__version__.split("+")[0].split(".")[:2])
    facts["torch_ok"] = major_minor >= (2, 4)     # nn.RMSNorm needs 2.4
    facts["tflops"]["cpu_fp32"] = matmul_tflops(torch, "cpu",
                                                torch.float32, 1024)
    facts["tflops"]["cpu_bf16"] = matmul_tflops(torch, "cpu",
                                                torch.bfloat16, 512, 0.5)
    if torch.cuda.is_available():
        facts["cuda"] = True
        facts["backend"] = "rocm" if getattr(torch.version, "hip", None) \
            else "cuda"
        props = torch.cuda.get_device_properties(0)
        facts["device_name"] = props.name
        facts["device_memory_gb"] = round(props.total_memory / 1e9, 1)
        facts["compute_capability"] = "%d.%d" % (props.major, props.minor)
        try:
            facts["bf16"] = bool(torch.cuda.is_bf16_supported())
        except Exception:
            facts["bf16"] = False
        facts["tflops"]["gpu_bf16"] = matmul_tflops(
            torch, "cuda", torch.bfloat16 if facts["bf16"] else torch.float16,
            4096)
        # RTX 50-series GPUs (compute capability 12) need a torch built
        # for CUDA 12.8 or newer (torch 2.7+)
        if facts["backend"] == "cuda" and props.major >= 12 \
                and major_minor < (2, 7):
            facts["warnings"].append(
                "This GPU (compute capability %d.%d) cannot run with torch "
                "%s. Install a torch build for CUDA 12.8 or newer, for "
                "example: py -m pip install --upgrade torch --index-url "
                "https://download.pytorch.org/whl/cu128"
                % (props.major, props.minor, torch.__version__))
    return facts


def choose_preset(facts):
    """build.py with no preset: full when a GPU is present, else pilot."""
    return "full" if facts.get("cuda") else "pilot"


def collect():
    facts = torch_facts()
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
        "compute_capability": facts["compute_capability"],
        "bf16": facts["bf16"],
        "tflops": facts["tflops"],
        "cpu_count": os.cpu_count(),
        "ram_gb": round(ram_gb() or 0, 1),
        "free_disk_gb": round(disk.free / 1e9, 1),
        "packages": package_versions(),
        "preset": choose_preset(facts),
        "warnings": facts["warnings"],
    }
    env["missing_required"] = [p for p in REQUIRED
                               if not env["packages"].get(p)]
    env["missing_optional"] = [p for p in ("hijridate",)
                               if not env["packages"].get(p)]
    return env


def show(env):
    speed = env.get("tflops") or {}
    rows = [
        ("Operating system", env["os"] + " / " + env["machine"]),
        ("Python", env["python"]),
        ("torch", "%s%s" % (env["torch"] or "NOT INSTALLED",
                            "" if env["torch_ok"] or not env["torch"]
                            else "  (too old: 2.4 or newer needed)")),
        ("GPU", ("%s, %s GB (%s, compute %s)" % (
            env["device_name"], env["device_memory_gb"],
            env["backend"].upper(), env["compute_capability"]))
         if env["gpu"] else "none - CPU only"),
        ("bf16", "yes" if env["bf16"] else "no"),
        ("CPUs", str(env["cpu_count"])),
        ("RAM", "%s GB" % env["ram_gb"]),
        ("Free disk", "%s GB" % env["free_disk_gb"]),
    ]
    for name, value in speed.items():
        rows.append(("speed " + name, "%s TFLOPS" % value
                     if value is not None else "n/a"))
    for name, version in env["packages"].items():
        rows.append(("  " + name, version or "missing"))
    rows.append(("build.py would choose", env["preset"]))
    width = max(len(r[0]) for r in rows)
    print("-" * 64)
    for name, value in rows:
        print("%-*s  %s" % (width, name, value))
    print("-" * 64)
    for warning in env.get("warnings") or []:
        print("WARNING: " + warning)
    if env["missing_required"]:
        print("Missing required packages: %s" % ", ".join(
            env["missing_required"]))
        if "torch" in env["missing_required"]:
            print("torch is never installed by these scripts. Install the")
            print("build that fits your machine (CUDA, ROCm or CPU) first.")
    if env["preset"] == "full" and (env["device_memory_gb"] or 0) < 8:
        print("Note: the full preset wants 8 GB of GPU memory or more.")


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

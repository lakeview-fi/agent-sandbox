"""Preflight: openshell usable, gateway connected, name free, image present. Returns checks, baseline, whether to continue."""
import shutil
from pathlib import Path

from .model import FAIL, INFO, PASS, Check
from .process import osh, phases, run


def preflight(name: str, args) -> tuple[list[Check], dict, bool]:
    checks, base = [], {}
    if not shutil.which("openshell"):
        return [Check("openshell on PATH", FAIL, "install per the platform file (ask the user first), then re-run")], base, False
    ver = osh("--version")
    base["version"] = ver.text.splitlines()[0] if ver.text else "unknown"
    checks.append(Check("openshell version", PASS if ver.code == 0 else FAIL, base["version"]))
    status = osh("status")
    connected = "Connected" in status.text
    checks.append(Check("gateway connected", PASS if connected else FAIL,
                        "Connected" if connected else f"{status.text[:300]} (see the platform file; may need the bash-sandbox bypass)"))
    base["phases"] = phases() if connected else {}
    free = name not in base["phases"]
    checks.append(Check("sandbox name free", PASS if free else FAIL, name))
    checks.append(Check("/dev/kvm (MicroVM possible?)", INFO, "present" if Path("/dev/kvm").exists() else "absent: Docker/Podman driver only, a weaker (shared-kernel) boundary; record this"))
    image_ok = True
    if args.image != "default":
        if shutil.which("docker"):
            image_ok = run(["docker", "image", "inspect", args.image]).code == 0
            checks.append(Check(f"image {args.image} present", PASS if image_ok else FAIL,
                                "found" if image_ok else "build it per SANDBOX-IMAGE.md, or use --image default (agent/node checks will SKIP)"))
        else:
            image_ok = False
            checks.append(Check("docker on PATH", FAIL, "needed to find the image; may be blocked by the agent's bash sandbox"))
    return checks, base, connected and free and image_ok

# AirTrack 1.0.0
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC


# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC

#!/usr/bin/env python3
# AirTrack 1.0.0 'Wilbur' — Release 300
# Copyright (c) 2025 Trevor (“Subhuti”). All rights reserved.
# SPDX-License-Identifier: LicenseRef-AirTrack-Proprietary-NC
import os
import platform
import subprocess
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))


def load_env(env_path):
    out = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            k, v = s.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def main():
    system = platform.system().lower()
    if "linux" in system or "darwin" in system:  # darwin treated same as linux
        script = os.path.join(HERE, "linux", "updater.sh")
        cmd = ["bash", script]
    elif "windows" in system:
        script = os.path.join(HERE, "windows", "Updater.ps1")
        # Run in PowerShell, bypass policy for current process only
        cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script,
        ]
    else:
        print(f"Unsupported OS: {platform.system()}", file=sys.stderr)
        sys.exit(2)
    # run from repo root so relative paths (VERSION/releases) resolve
    proc = subprocess.run(cmd, cwd=ROOT)
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()

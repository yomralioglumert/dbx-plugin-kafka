#!/usr/bin/env python3
"""Cross-compile Go payloads and sign with the reviewed DBX Store packager.

This downstream helper never changes upstream release identity, installs trust
keys, or deploys a package. Native per-platform runtime CI remains a separate gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
TARGETS = {
    "linux-x64": ("linux", "amd64"),
    "linux-arm64": ("linux", "arm64"),
    "darwin-x64": ("darwin", "amd64"),
    "darwin-arm64": ("darwin", "arm64"),
    "windows-x64": ("windows", "amd64"),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packager", type=Path, required=True)
    parser.add_argument("--signing-env", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "manifest.json").read_text())
    version = manifest["version"]
    if "-alba." not in version:
        raise SystemExit("A distinct Alba prerelease version is required")
    if not (ROOT / "ui/index.html").is_file():
        raise SystemExit("Build and verify ui/index.html first")
    if stat.S_IMODE(args.signing_env.stat().st_mode) != 0o600:
        raise SystemExit("Signing environment file must have mode 0600")
    secrets = {}
    for line in args.signing_env.read_text().splitlines():
        line = line.strip().removeprefix("export ")
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        secrets[key] = shlex.split(value)[0]
    required = {"DBX_PLUGIN_SIGNING_KEY", "DBX_PLUGIN_SIGNING_PUBLIC_KEY", "DBX_PLUGIN_SIGNING_KEY_ID"}
    if not required.issubset(secrets):
        raise SystemExit("Signing environment is incomplete")
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise SystemExit("Output must be empty; never replace a version's published bytes")
    build_env = {key: value for key, value in os.environ.items() if not key.startswith("DBX_PLUGIN_SIGNING_")}
    records = []
    for target, (goos, goarch) in TARGETS.items():
        print(f"Building and signing {target}", flush=True)
        with tempfile.TemporaryDirectory(prefix="dbx-alba-payload-") as directory:
            payload = Path(directory)
            binary_name = "dbx-plugin-kafka" + (".exe" if goos == "windows" else "")
            binary = payload / "bin" / target / binary_name
            binary.parent.mkdir(parents=True)
            env = {**build_env, "GOOS": goos, "GOARCH": goarch, "CGO_ENABLED": "0"}
            subprocess.run([
                "go", "build", "-trimpath", "-ldflags", f"-s -w -X=main.version={version}",
                "-o", str(binary), ".",
            ], cwd=ROOT / "backend", env=env, check=True)
            for name in ("assets", "ui"):
                shutil.copytree(ROOT / name, payload / name)
            shutil.copyfile(ROOT / "LICENSE", payload / "LICENSE")
            packaged = json.loads(json.dumps(manifest))
            packaged["entrypoints"]["backend"]["executable"] = f"bin/{target}/{binary_name}"
            (payload / "manifest.json").write_text(json.dumps(packaged, ensure_ascii=False, indent=2) + "\n")
            filename = f"{manifest['id']}-{version}-{target}.dbxp"
            unsigned = payload.parent / (payload.name + "-unsigned.dbxp")
            output = args.output / filename
            artifact_url = f"{manifest['source']}/releases/download/kafka-v{version}/{filename}"
            try:
                subprocess.run([str(args.packager), str(payload), str(unsigned)], env=build_env, check=True)
                signing_env = {**build_env, **{key: value for key, value in secrets.items() if key.startswith("DBX_PLUGIN_SIGNING_")}}
                subprocess.run([
                    str(args.packager), "sign", str(unsigned), str(output),
                    "--key-id", secrets["DBX_PLUGIN_SIGNING_KEY_ID"],
                    "--artifact-metadata", str(output.with_suffix(".artifact.json")),
                    "--target", target, "--artifact-url", artifact_url,
                ], env=signing_env, check=True)
            finally:
                unsigned.unlink(missing_ok=True)
            with zipfile.ZipFile(output) as archive:
                assert "signature.json" in archive.namelist()
                checksums = json.loads(archive.read("checksums.json"))["files"]
                for name, expected in checksums.items():
                    assert hashlib.sha256(archive.read(name)).hexdigest() == expected
                assert json.loads(archive.read("manifest.json"))["version"] == version
            records.append(json.loads(output.with_suffix(".artifact.json").read_text()))
    (args.output / "artifacts.json").write_text(json.dumps(records, indent=2) + "\n")
    public = {"keyId": secrets["DBX_PLUGIN_SIGNING_KEY_ID"], "publicKey": secrets["DBX_PLUGIN_SIGNING_PUBLIC_KEY"]}
    (args.output / "repository-public-key.json").write_text(json.dumps(public, indent=2) + "\n")
    print(f"Produced {len(records)} signed review artifacts; native CI and deployment are separate gates")


if __name__ == "__main__":
    main()

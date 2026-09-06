# -*- mode: python ; coding: utf-8 -*-

import os
import re
import sys
import zipfile
from pathlib import Path

from PyInstaller.config import CONF


package_root = Path(SPECPATH).resolve().parent
source_revision = os.environ.get("SKILL_MANAGER_SOURCE_REVISION", "")
if not re.fullmatch(r"[0-9a-f]{40}", source_revision):
    raise ValueError("SKILL_MANAGER_SOURCE_REVISION must be a full lowercase Git object ID")
generated_root = Path(CONF["workpath"]) / "generated"
generated_root.mkdir(parents=True, exist_ok=True)
(generated_root / "_skill_manager_build_identity.py").write_text(
    f"SOURCE_REVISION = {source_revision!r}\n"
)

analysis = Analysis(
    [str(package_root / "packaging" / "entrypoint.py")],
    pathex=[str(generated_root), str(package_root / "src")],
    binaries=[],
    datas=[],
    hiddenimports=["_skill_manager_build_identity"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# PyInstaller 6.21 emits base_library.zip in module-graph discovery order. A
# cold graph and a warm graph contain identical entries but can order them
# differently, which changes the one-file artifact. Canonicalize this single
# upstream archive at the build boundary before it enters the executable.
for destination, source, _kind in analysis.datas:
    if destination != "base_library.zip":
        continue
    source_path = Path(source)
    canonical_path = source_path.with_suffix(".canonical.zip")
    with zipfile.ZipFile(source_path, "r") as existing:
        entries = [(name, existing.read(name)) for name in sorted(existing.namelist())]
    with zipfile.ZipFile(canonical_path, "w") as canonical:
        for name, content in entries:
            canonical.writestr(zipfile.ZipInfo(name), content)
    os.replace(canonical_path, source_path)

python_archive = PYZ(analysis.pure)

platform_options = {}
if sys.platform == "darwin":
    platform_options.update(
        argv_emulation=False,
        target_arch="arm64",
        codesign_identity=os.environ.get("SKILL_MANAGER_CODESIGN_IDENTITY"),
        entitlements_file=None,
    )

executable = EXE(
    python_archive,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="skill-manager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    **platform_options,
)

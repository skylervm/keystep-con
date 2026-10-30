#!/bin/sh
# Build both models and run the offline firmware, bridge, and installer checks.
# Needs firmware/keystep-pro_Firmware_Update_2.5.20.0.kspf (Arturia's official update, not included).
set -e
cd "$(dirname "$0")/../tools"
PY="${PYTHON:-python3}"
"$PY" build_ksp_patch.py --model both
"$PY" test_model_hooks.py --model original
"$PY" test_model_hooks.py --model chroma
"$PY" test_tempo_paths.py
"$PY" test_tempo_hooks.py
"$PY" test_display_paths.py
"$PY" test_foreground_paths.py
"$PY" test_tempo_feedback.py
"$PY" test_tempo_concurrency.py
"$PY" test_package_metadata.py
"$PY" -m unittest discover -s ../tests -v
N=$(sed -n 's/^PATCH_BUILD = \([0-9]*\).*/\1/p' build_ksp_patch.py)
"$PY" -c "import zipfile;z=zipfile.ZipFile('../firmware/patched/KSCON_2.5.99_build$N.kspf');assert z.testzip() is None;print('package ok: firmware/patched/KSCON_2.5.99_build$N.kspf')"
# the page's firmware patcher: regenerate its changed-bytes file and check the page makes this exact build
"$PY" make_web_patch.py > ../web/src/1f-fwpatch.js
sh ../web/build.sh
"$PY" test_web_patch.py ../web

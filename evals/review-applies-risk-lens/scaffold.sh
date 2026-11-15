#!/usr/bin/env bash
set -euo pipefail
bash "$(dirname "$0")/../fixtures/make-shop.sh" review
DATA=".ravend-home/projects/example.com-acme-shop"
python3 - "$DATA" <<'PY'
import json, sys
from pathlib import Path
data = Path(sys.argv[1])
profile = json.loads((data / "profile.json").read_text())
profile["risk"] = [{"name": "checkout", "paths": ["src/cart.js"], "lenses": ["money"]}]
(data / "profile.json").write_text(json.dumps(profile, indent=2))
(data / "specs" / "cart-coupon" / "state.json").write_text(json.dumps({"approvals": [{"at": "2026-11-05T10:00:00", "note": "approved"}]}))
PY

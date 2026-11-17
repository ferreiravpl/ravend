#!/usr/bin/env bash
# shop (this workspace) + a sibling library ../pricing with its own Ravend profile.
set -euo pipefail
bash "$(dirname "$0")/../fixtures/make-shop.sh" base
LIB="../pricing"
rm -rf "$LIB" && mkdir -p "$LIB/src" "$LIB/test"
cat > "$LIB/package.json" <<'JSON'
{ "name": "pricing", "private": true, "type": "module", "scripts": { "test": "node --test" } }
JSON
cat > "$LIB/src/price.js" <<'JS'
/** Unit price in cents for a sku. */
export function unitPrice(catalog, sku) {
  return catalog[sku];
}
JS
cat > "$LIB/test/price.test.js" <<'JS'
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { unitPrice } from '../src/price.js';
test('unit price', () => assert.equal(unitPrice({ A: 500 }, 'A'), 500));
JS
( cd "$LIB" && git init -q -b main && git config user.email eval@example.com && git config user.name eval \
  && git remote add origin https://example.com/acme/pricing.git && git add -A && git commit -qm "initial pricing" )
DATA=".ravend-home/projects/example.com-acme-pricing"
mkdir -p "$DATA/specs" "$DATA/state"
cat > "$DATA/profile.json" <<'JSON'
{
  "version": 1,
  "stacks": ["node"],
  "git": { "base_branch": "main", "branch_prefix": "feat/" },
  "gate": { "fast": [ { "name": "unit", "run": "node --test" } ], "full": [ { "name": "unit", "run": "node --test" } ] }
}
JSON

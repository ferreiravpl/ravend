#!/usr/bin/env bash
# Builds the "shop" fixture in the current directory (the eval workspace).
#   make-shop.sh base     -> repo + local Ravend profile
#   make-shop.sh spec     -> base + approved small spec "cart-coupon"
#   make-shop.sh review   -> spec + feature branch with an implementation containing a boundary bug
# Ravend data goes to ./.ravend-home (RAVEND_HOME in case.yaml), excluded from git.
set -euo pipefail
variant="${1:-base}"
git init -q -b main
git config user.email eval@example.com
git config user.name eval
git remote add origin https://example.com/acme/shop.git
echo ".ravend-home/" >> .git/info/exclude

mkdir -p src test
cat > package.json <<'EOF'
{ "name": "shop", "private": true, "type": "module", "scripts": { "test": "node --test" } }
EOF
cat > src/cart.js <<'EOF'
/** Total of the cart in cents. items: [{ sku, price, qty }] */
export function total(items) {
  return items.reduce((sum, item) => sum + item.price * item.qty, 0);
}

export function label(items) {
  return `Total: ${total(items)}`;
}
EOF
cat > test/cart.test.js <<'EOF'
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { total, label } from '../src/cart.js';

test('total sums price * qty', () => {
  assert.equal(total([{ sku: 'A', price: 500, qty: 2 }, { sku: 'B', price: 100, qty: 1 }]), 1100);
});

test('label shows the total', () => {
  assert.equal(label([{ sku: 'A', price: 100, qty: 1 }]), 'Total: 100');
});
EOF
git add -A && git commit -qm "initial shop"

DATA=".ravend-home/projects/example.com-acme-shop"
mkdir -p "$DATA/specs" "$DATA/knowledge" "$DATA/runs" "$DATA/state"
cat > "$DATA/profile.json" <<'EOF'
{
  "version": 1,
  "stacks": ["node"],
  "git": { "base_branch": "main", "branch_prefix": "feat/", "commit_per_task": true },
  "protected_paths": [".env"],
  "gate": {
    "fast": [ { "name": "unit", "run": "node --test", "when": ["src/*", "test/*"] } ],
    "full": [ { "name": "unit", "run": "node --test" } ]
  }
}
EOF
cat > "$DATA/project.md" <<'EOF'
# shop
- Plain Node ESM, no dependencies. Tests: node:test + node:assert/strict in test/*.test.js.
- Money is always integer cents.
EOF
[ "$variant" = "base" ] && exit 0

mkdir -p "$DATA/specs/cart-coupon"
cat > "$DATA/specs/cart-coupon/spec.md" <<'EOF'
---
slug: cart-coupon
title: Coupon SAVE10 on cart total
tier: small
status: approved
source: prompt
branch: feat/cart-coupon
created: 2026-11-05
---

# Coupon SAVE10 on cart total

## Problem
Customers cannot apply coupons. Marketing needs SAVE10: 10% off carts of 10000 cents or more.

## Acceptance criteria
- AC1 [unit]: Given a cart totaling 10000 cents or more, when total(items, "SAVE10") is computed, then the result is 90% of the total, rounded down to whole cents.
- AC2 [unit]: Given a cart totaling less than 10000 cents, when total(items, "SAVE10") is computed, then no discount is applied.
- AC3 [unit]: Given any cart, when total(items, "NOPE") is computed, then it throws an Error with message "invalid coupon".

## Out of scope
- Other coupon codes, persistence, UI.

## Tasks
- [ ] T1: Add optional coupon parameter to total — files: src/cart.js, test/cart.test.js — proves: AC1, AC2, AC3 — deps: none

## Log
- 2026-11-05 spec created (tier small)
EOF
[ "$variant" = "spec" ] && exit 0

git switch -q -c feat/cart-coupon
cat > src/cart.js <<'EOF'
/** Total of the cart in cents. items: [{ sku, price, qty }] */
export function total(items, coupon) {
  const gross = items.reduce((sum, item) => sum + item.price * item.qty, 0);
  if (coupon === undefined) return gross;
  if (coupon !== 'SAVE10') throw new Error('invalid coupon');
  return gross > 10000 ? Math.floor(gross * 0.9) : gross;
}

export function label(items) {
  return `Total: ${total(items)}`;
}
EOF
cat >> test/cart.test.js <<'EOF'

test('SAVE10 gives 10% off big carts', () => {
  assert.equal(total([{ sku: 'A', price: 20000, qty: 1 }], 'SAVE10'), 18000);
});

test('SAVE10 does nothing on small carts', () => {
  assert.equal(total([{ sku: 'A', price: 500, qty: 1 }], 'SAVE10'), 500);
});

test('unknown coupon throws', () => {
  assert.throws(() => total([], 'NOPE'), /invalid coupon/);
});
EOF
git add -A && git commit -qm "feat(cart): coupon SAVE10 [cart-coupon T1]"
sed -i 's/- \[ \] T1/- [x] T1/' "$DATA/specs/cart-coupon/spec.md"
sed -i 's/^status: approved/status: review/' "$DATA/specs/cart-coupon/spec.md"

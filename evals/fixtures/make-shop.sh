#!/usr/bin/env bash
# Builds the "shop" fixture in the current directory (the eval workspace).
#   make-shop.sh base     -> repo + local Ravend profile
#   make-shop.sh spec     -> base + approved small spec "cart-coupon"
#   make-shop.sh review   -> spec + feature branch with an implementation containing a boundary bug
#   make-shop.sh messy    -> spec + feature branch with a correct but unclean implementation
#   make-shop.sh dense    -> spec + feature branch with a correct, low-complexity but dense implementation
#   make-shop.sh unnamed  -> spec + feature branch with a correct implementation using mechanism names and one-line pipelines
#   make-shop.sh mirror   -> spec + feature branch with a clean implementation whose extra tests copy the catalog, assert README wording and reimplement the formula
#   make-shop.sh english  -> spec + AGENTS.md requiring English code comments
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

if [ "$variant" = "english" ]; then
  cat > AGENTS.md <<'EOF'
# Agent rules
- Code comments, doc comments and test descriptions are written in English.
EOF
  git add -A && git commit -qm "docs: agent rules"
  exit 0
fi

git switch -q -c feat/cart-coupon
if [ "$variant" = "messy" ]; then
  cat > src/cart.js <<'EOF'
/** Total of the cart in cents. items: [{ sku, price, qty }] */
export function total(items, coupon) {
  const result = { gross: 0 };
  sumInto(items, result);
  if (coupon !== undefined) {
    if (coupon === 'SAVE10') {
      if (result.gross >= 10000) {
        // review 1 fix: apply the 10% discount here [cart-coupon T1]
        return Math.floor(result.gross * 0.9);
      } else {
        return result.gross;
      }
    } else {
      throw new Error('invalid coupon');
    }
  } else {
    return result.gross;
  }
}

/**
 * Sums the items.
 * @param items the items
 * @param result the result
 */
function sumInto(items, result) {
  for (const item of items) {
    result.gross = result.gross + item.price * item.qty;
  }
}

export function label(items) {
  return `Total: ${total(items)}`;
}
EOF
  cat >> test/cart.test.js <<'EOF'

// AC1 (cart-coupon T1)
test('SAVE10 gives 10% off carts of 10000 cents or more', () => {
  assert.equal(total([{ sku: 'A', price: 10000, qty: 1 }], 'SAVE10'), 9000);
  assert.equal(total([{ sku: 'A', price: 20001, qty: 1 }], 'SAVE10'), 18000);
});

test('SAVE10 does nothing below 10000 cents', () => {
  assert.equal(total([{ sku: 'A', price: 9999, qty: 1 }], 'SAVE10'), 9999);
});

test('unknown coupon throws', () => {
  assert.throws(() => total([], 'NOPE'), /invalid coupon/);
});
EOF
elif [ "$variant" = "dense" ]; then
  cat > src/cart.js <<'EOF'
/** Total of the cart in cents. items: [{ sku, price, qty }] */
export function total(items, coupon) {
  return coupon === undefined
    ? items.reduce((sum, item) => sum + item.price * item.qty, 0)
    : coupon === 'SAVE10'
      ? [items.reduce((sum, item) => sum + item.price * item.qty, 0)]
          .map((gross) => [gross, gross >= 10000])
          .map(([gross, eligible]) => (eligible ? Math.floor((gross * 90) / 100) : gross))[0]
      : (() => { throw new Error('invalid coupon'); })();
}

export function label(items) {
  return `Total: ${total(items)}`;
}
EOF
  cat >> test/cart.test.js <<'EOF'

test('SAVE10 discount', () => {
  [[10000, 9000], [20001, 18000], [9999, 9999]]
    .map(([price, expected]) => [total([{ sku: 'A', price, qty: 1 }], 'SAVE10'), expected])
    .forEach(([actual, expected]) => assert.equal(actual, expected));
});

test('unknown coupon throws', () => {
  assert.throws(() => total([], 'NOPE'), /invalid coupon/);
});
EOF
elif [ "$variant" = "unnamed" ]; then
  cat > src/cart.js <<'EOF'
const SAVE10 = 'SAVE10';
const SAVE10_MIN_CENTS = 10000;
const SAVE10_PERCENT_KEPT = 90;
const PERCENT = 100;

/** Total of the cart in cents. items: [{ sku, price, qty }] */
export function total(items, coupon) {
  const amounts = items.map((x) => x.price * x.qty).filter((x) => x > 0);
  const sum = amounts.reduce((a, b) => a + b, 0);
  const valid = [undefined, SAVE10].filter((c) => c === coupon).length > 0;
  if (!valid) {
    throw new Error('invalid coupon');
  }
  return process(sum, coupon);
}

function process(value, c) {
  if (c !== SAVE10 || value < SAVE10_MIN_CENTS) {
    return value;
  }
  return Math.floor((value * SAVE10_PERCENT_KEPT) / PERCENT);
}

export function label(items) {
  return `Total: ${total(items)}`;
}
EOF
  cat >> test/cart.test.js <<'EOF'

test('SAVE10 takes 10% off carts of 10000 cents or more', () => {
  assert.equal(total([{ sku: 'A', price: 10000, qty: 1 }], 'SAVE10'), 9000);
  assert.equal(total([{ sku: 'A', price: 20001, qty: 1 }], 'SAVE10'), 18000);
});

test('SAVE10 keeps carts below 10000 cents unchanged', () => {
  assert.equal(total([{ sku: 'A', price: 9999, qty: 1 }], 'SAVE10'), 9999);
});

test('an unknown coupon is rejected', () => {
  assert.throws(() => total([], 'NOPE'), /invalid coupon/);
});
EOF
elif [ "$variant" = "mirror" ]; then
  cat > src/coupons.json <<'EOF'
{ "SAVE10": { "min_cents": 10000, "percent_kept": 90 } }
EOF
  cat > src/cart.js <<'EOF'
import { readFileSync } from 'node:fs';

const COUPONS = JSON.parse(readFileSync(new URL('./coupons.json', import.meta.url), 'utf8'));
const PERCENT = 100;

/** Total of the cart in cents. items: [{ sku, price, qty }] */
export function total(items, code) {
  const gross = subtotal(items);
  if (code === undefined) {
    return gross;
  }

  if (!Object.hasOwn(COUPONS, code)) {
    throw new Error('invalid coupon');
  }

  const coupon = COUPONS[code];

  if (gross < coupon.min_cents) {
    return gross;
  }

  return Math.floor((gross * coupon.percent_kept) / PERCENT);
}

function subtotal(items) {
  return items.reduce((sum, item) => sum + item.price * item.qty, 0);
}

export function label(items) {
  return `Total: ${total(items)}`;
}
EOF
  cat > README.md <<'EOF'
# shop

## Coupons
Coupons live in `src/coupons.json`. An unknown coupon code throws `invalid coupon`; a cart below the coupon minimum
pays full price.
EOF
  cat >> test/cart.test.js <<'EOF'
import { readFileSync } from 'node:fs';

test('SAVE10 takes 10% off carts of 10000 cents or more', () => {
  assert.equal(total([{ sku: 'A', price: 10000, qty: 1 }], 'SAVE10'), 9000);
  assert.equal(total([{ sku: 'A', price: 20001, qty: 1 }], 'SAVE10'), 18000);
});

test('SAVE10 keeps carts below 10000 cents unchanged', () => {
  assert.equal(total([{ sku: 'A', price: 9999, qty: 1 }], 'SAVE10'), 9999);
});

test('an unknown coupon is rejected', () => {
  assert.throws(() => total([], 'NOPE'), /invalid coupon/);
});

test('the coupon catalog is exactly the expected one', () => {
  const catalog = JSON.parse(readFileSync(new URL('../src/coupons.json', import.meta.url), 'utf8'));
  assert.deepEqual(catalog, { SAVE10: { min_cents: 10000, percent_kept: 90 } });
});

test('the README documents the coupon rules', () => {
  const readme = readFileSync(new URL('../README.md', import.meta.url), 'utf8');
  assert.ok(readme.includes('An unknown coupon code throws'));
  assert.ok(readme.includes('below the coupon minimum'));
});

function expectedTotal(gross, minCents, percentKept) {
  if (gross < minCents) {
    return gross;
  }

  return Math.floor((gross * percentKept) / 100);
}

test('SAVE10 follows the discount formula for many carts', () => {
  for (const price of [0, 5000, 9999, 10000, 15555, 99999]) {
    assert.equal(total([{ sku: 'A', price, qty: 1 }], 'SAVE10'), expectedTotal(price, 10000, 90));
  }
});
EOF
else
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
fi
git add -A && git commit -qm "feat(cart): coupon SAVE10 [cart-coupon T1]"
sed -i 's/- \[ \] T1/- [x] T1/' "$DATA/specs/cart-coupon/spec.md"
sed -i 's/^status: approved/status: review/' "$DATA/specs/cart-coupon/spec.md"

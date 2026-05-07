# Milestone 2 — Work Briefing for Code Audit & Testing

## Project Context

This is a university project (IST, Communications Security) implementing a **privacy-preserving dark auction** using MP-SPDZ (Multi-Party Computation framework). 3 parties submit secret buy/sell orders for 3 assets (BTC, ETH, SOL), and the MPC program computes a uniform clearing price + pro-rata allocation without revealing individual orders.

## Current State

- `dark_auction.mpc` — working baseline, tested with N_ORDERS=5, seeds 123/124/125
- `simulator/dark_auction_sim.py` — clear-text reference implementation, outputs match MPC
- `scripts/generate_inputs.py` — generates random inputs (human-readable + MP-SPDZ format)
- `scripts/auto_compare.py` — automated harness to compare simulator across seeds
- Tested only with MASCOT protocol so far

## Milestone 2 Spec Requirements (from PROJECT-STATEMENT.txt)

The program MUST:
1. Read each party's private orders using `sint.get_input_from(party_id)`
2. Support 3 assets (BTC, ETH, SOL) with **N_ORDERS = 10** buy/sell orders per party per asset
3. Find the clearing price by scanning a discrete price ladder, computing D(p) and S(p)
4. Handle midpoint tie-break: `p* = (p_low + p_high) / 2`
5. Pro-rata allocation as described (floor division + leftover to first eligible)
6. Reveal ONLY final results (clearing price, volume, fills) — intermediate order data must remain secret

## Known Gaps / Issues to Fix

### 1. N_ORDERS=10 not tested
The code auto-detects N_ORDERS from input files, so it should work. But we need to:
- Generate inputs with `--n-orders 10`
- Verify compilation succeeds (more prices = longer compilation)
- Verify simulator and MPC still match

### 2. Midpoint tie-break for odd sums
Current code (line 107): `sum_ph = p_low + p_high` then prints `price_low` and `price_high`.
The spec says clearing_price = (p_low + p_high) / 2. If sum is odd, this should be a half-integer (e.g., 104.5). The current code doesn't compute or print the actual midpoint clearing price — it just prints both bounds. Should print `sum_ph // 2` or handle the `.5` case.

### 3. Privacy concern — D(p) and S(p) revealed
Lines 71-72 reveal D(p) and S(p) for every price in the ladder. This is a deliberate trade-off (avoids expensive secret comparisons), but:
- The report must JUSTIFY why this is acceptable
- We should document exactly what information leaks (aggregate demand/supply curves)
- Ideally discuss how to avoid it (at what cost)

### 4. Edge cases not tested
- No matching orders (all buys below all asks) → should output traded=0
- Single order per side → trivial clearing
- All orders at same price → p_low == p_high
- One party has no orders for an asset (all zeros)

### 5. Code polish needed
- No docstring or header comment explaining the algorithm
- Section comments are minimal
- Variable names could be clearer in some places (e.g., `_bp`, `_ap` are discarded)

## File Locations

```
dark_auction.mpc              — main MPC program (167 lines)
simulator/dark_auction_sim.py — reference simulator (141 lines)
scripts/generate_inputs.py    — input generator
scripts/auto_compare.py       — automated comparison harness
inputs/party{0,1,2}.txt       — human-readable inputs
Inputs/Input-P{0,1,2}-0       — MP-SPDZ binary inputs
RUNS/dark_auction_run_log.md  — existing run log
```

## Algorithm Summary (as implemented)

1. **Compile-time**: Read prices from `Inputs/Input-P{id}-0` files (public)
2. **Runtime**: Read secret quantities via `sint.get_input_from(pid)`
3. **Per asset**:
   - Collect all unique non-zero prices from bids and asks
   - For each price p: compute D(p) = sum of secret bid quantities where bid_price >= p
   - For each price p: compute S(p) = sum of secret ask quantities where ask_price <= p
   - Reveal D(p) and S(p), compute V(p) = min(D,S)
   - Find best_V = max over all V(p)
   - Find p_low and p_high (price range achieving best_V)
   - At p_low: determine rationed side (buy if D > S, else sell)
   - Pro-rata: for each eligible order, share = floor(q * V* / total_pool)
   - Distribute leftover units to first N eligible orders
4. **Output**: clearing price bounds, traded volume, per-party fills

## .reveal() Calls Inventory

| Line | What's revealed | Why | Leakage |
|------|----------------|-----|---------|
| 71 | D(p) for each price p | Need public value to compare D vs S and find max V | Aggregate demand curve shape |
| 72 | S(p) for each price p | Same as above | Aggregate supply curve shape |
| 145 | share (per-order pro-rata fill) | Need public value for integer leftover distribution | Individual order's proportional share |

## What the Report Must Cover

1. **Design decisions**: Why prices are public (compile-time), quantities are secret
2. **Algorithm description**: Clearing price computation, pro-rata allocation
3. **.reveal() analysis**: Every reveal justified, what leaks, what stays private
4. **Correctness verification**: Test results across multiple seeds/sizes
5. **Privacy trade-offs**: What an adversary learns from revealed D(p)/S(p) aggregates

## Deliverables Checklist

- [ ] `dark_auction.mpc` — polished, commented, handles edge cases
- [ ] Correctness verified with N_ORDERS=10 (multiple seeds)
- [ ] Edge case tests documented
- [ ] Clear-text simulator matches MPC for all test cases
- [ ] Report section written (design + .reveal() analysis + results)
- [ ] Demo script ready (step-by-step commands for live demo)

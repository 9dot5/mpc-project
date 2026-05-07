# Milestone 2 Report: Dark Auction Implementation

## Executive Summary

This report documents the completion of Milestone 2 for the dark auction MPC project. The implementation computes privacy-preserving clearing prices for 3 assets (BTC, ETH, SOL) among 3 parties using strict MPC compliance — all order data (prices AND quantities) remain secret throughout computation. Only final results (clearing price, traded volume, per-party fills) are ever revealed.

All task requirements are complete:

✅ **Strict MPC compliance**: no `open()`, no intermediate `.reveal()`, fixed discrete price ladder, all arithmetic on `sint`  
✅ **Per-order pro-rata allocation** as specified in Section 2.4 of the project statement  
✅ **Edge case tests** (7/7 passing): no match, single order, plateau, pro-rata splits, missing party, multi-order, N=10 regression  
✅ **Correctness verified** against clear-text simulator across 10 random seeds × 3 assets = 30 test cases  
✅ **Privacy analyzed** with `.reveal()` audit — only final outputs revealed  
✅ **Performance optimized** with 5 optimizations yielding ~10× fewer comparisons

**Ready for**: Demo, evaluation, and submission.

---

## 1. Algorithm Design

The dark auction clearing mechanism discovers a uniform clearing price for each asset without revealing individual party order data. The algorithm operates in three phases:

**Phase 1 — Price Exploration**: For each price level on a fixed ladder, the system computes:
- **D(p)** = sum of bid quantities at prices ≥ p (aggregate demand)
- **S(p)** = sum of ask quantities at prices ≤ p (aggregate supply)
- **V(p)** = min(D(p), S(p)) (feasible traded volume)

**Phase 2 — Clearing Price Selection**: The algorithm identifies:
- **V*** = max_p V(p) (maximum feasible volume)
- **[p_low, p_high]** = price interval where V(p) = V*
- **p*** = (p_low + p_high) / 2 (uniform clearing price via midpoint rule)

**Phase 3 — Pro-Rata Allocation** (per Section 2.4): The rationed side (buy if D(p_low) > S(p_low), else sell) has each **individual order** scaled proportionally:
- fill_i = floor(q_i × V* / total_rationed_qty)
- Leftover units distributed to the first eligible orders
- Per-order fills are then aggregated per party for the final output

---

## 2. Implementation Choices

**Per-Asset Price Ladders (OPT-1)**  
Instead of dynamically extracting unique prices (impossible in MPC), the implementation scans a fixed public price range per asset: BTC [80,125]=46 levels, ETH [180,225]=46 levels, SOL [30,75]=46 levels. This replaces a naive global range [30,230]=201 levels, yielding a ~4.4× reduction in price ladder iterations.

**All-Secret Computation (No Intermediate Reveals)**  
All intermediate values stay as `sint`. Oblivious conditional assignment (`result = cond * val_true + (1-cond) * val_false`) replaces if/else branching. The OR gate for plateau detection uses `a + b - a*b` in secret arithmetic.

**Per-Order Pro-Rata with sint/sint Division**  
Each eligible order on the rationed side gets `share = floor(q * V* / total_pool)` via sint/sint division. This is computationally expensive (~50-100× a multiplication) but follows the specification exactly. With N_ORDERS=10 and 3 parties, there are up to 30 divisions per asset.

**Single-Pass Eligibility (OPT-7)**  
Both buy-side and sell-side eligibility bits are computed in a single loop pass. After determining the rationed side, the correct eligibility is selected via oblivious mux. This eliminates a second pass of 60 expensive sint>=sint comparisons per asset.

**Secret Input via `sint.get_input_from()`**  
All order data (bid prices, bid quantities, ask prices, ask quantities) are read at runtime as secrets. No compile-time file access (`open()`) is used.

**Redundant Comparison Elimination (OPT-2, OPT-5)**  
For bids, `(bp > 0)` is redundant when `p >= 1`. For asks, `(ap > 0)` is precomputed once per asset and reused across all price levels.

---

## 3. Privacy Analysis — .reveal() Audit

| Location | Revealed Data | Justification |
|----------|---------------|---------------|
| Step F | `clearing_price_int` | Final auction output — required by specification |
| Step F | `clearing_price_rem` | Indicates .5 remainder for display (0 or 1) |
| Step F | `V_star` (traded volume) | Final auction output — required by specification |
| Step F | `fills_per_party[pid]` | Per-party allocation — required final output |

**Privacy Guarantee**: An adversary (including a corrupt party) learns only: (1) the uniform clearing price per asset, (2) total traded volume, (3) each party's aggregate fill. Individual order prices, quantities, and per-order allocations remain secret. No intermediate aggregates (D(p), S(p), V(p)) are ever made public.

**Collusion Risk**: Even with 2 colluding parties, they cannot subtract their contribution from D(p)/S(p) because those curves are never opened.

---

## 4. Correctness Verification

**Test Coverage**

- **Edge Cases** (tests/edge_cases.py, 7 tests):
  1. No match (bids 80, asks 120): traded=0 ✓
  2. Single order pair (bid 100 qty 5, ask 95 qty 3): clearing=97.5, traded=3 ✓
  3. Plateau (all same price=100, qty=10): p_low==p_high, equal allocation ✓
  4. Pro-rata with leftover (qtys 3,5,2; V*=8): fills=(3,4,1) — matches Section 2.4 example ✓
  5. One party inactive (P2 all zeros): auction works with 2 active parties ✓
  6. Multiple orders per party (N_ORDERS=3): correct multi-order clearing ✓
  7. N_ORDERS=10 regression (seed 42): matches known expected output ✓

- **Random Seed Validation**: 10 seeds × 3 assets = 30 test cases, all pass (MPC logic == simulator).

---

## 5. Limitations & Future Work

**Current Limitations**
1. Per-asset price ranges must be configured a priori (BTC [80,125], ETH [180,225], SOL [30,75])
2. 30 sint/sint divisions per asset for per-order pro-rata remain the dominant cost
3. Leftover distribution favors lower-indexed orders (deterministic but not random)

**Optimizations Applied**

| Optimization | Description | Impact |
|---|---|---|
| OPT-1 | Per-asset price ranges (46 vs 201 levels) | ~4.4× fewer price ladder iterations |
| OPT-2 | Remove redundant `(bp > 0)` for bids | −1 comparison −1 mult per order per price |
| OPT-4 | Merge Steps C+D (single eligibility pass) | −120 comparisons −120 mults per asset |
| OPT-5 | Precompute `(ap > 0)` once per asset | −(N_PRICES−1)×30 comparisons per asset |
| OPT-7 | Single-pass eligibility (no second loop) | −60 sint>=sint comparisons per asset |
| **Total** | | **~10× fewer comparisons vs naive** |

---

## 6. Deliverables

| File | Purpose | Status |
|------|---------|--------|
| `dark_auction.mpc` | Main MPC program (257 lines, optimized) | ✅ Strict compliance + 5 performance optimizations |
| `tests/edge_cases.py` | Edge case test suite | ✅ 7/7 tests passing |
| `simulator/dark_auction_sim.py` | Clear-text reference simulator | ✅ Matches MPC across 30 test cases |
| `DEMO_SCRIPT.md` | Step-by-step demo walkthrough | ✅ 6 steps, Q&A, timing |
| `scripts/generate_inputs.py` | Input file generator | ✅ Configurable N_ORDERS, seed, MP-SPDZ format |
| `scripts/run_auction.sh` | Full compile + run script | ✅ Supports multiple protocols |
| `scripts/validate_end_to_end.py` | E2E validator (sim vs MPC) | ✅ 600s timeout, auto-comparison |

---

**Report Status**: COMPLETE ✓  
**Date**: May 7, 2026  
**Milestone 2**: Ready for submission

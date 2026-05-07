# Hand-Verified Test Scenarios — Milestone 2

**Requirement** (Section 4, Milestone 2, item 3):
> "Verify correctness: construct a small test case (≤ 4 orders per side, 1 asset)
> where you can compute the clearing price, volume and fills by hand.
> Show that the program output matches."

Each scenario below uses ≤ 4 orders per side, 1 asset (asset 0 only; assets 1–2 are empty).
Input files are in `tests/scenarios/<scenario_name>/Input-P{0,1,2}-0`.
All results verified against the simulator (`simulator/dark_auction_sim.py`).

---

## Scenario 1: Basic overlap — 1 bid, 1 ask

**Orders:**

| Party | Side | Price | Qty |
|-------|------|-------|-----|
| P0    | Bid  | 100   | 5   |
| P1    | Ask  | 90    | 3   |

**Hand computation:**

| p   | D(p) | S(p) | V(p) |
|-----|------|------|------|
| 90  | 5    | 3    | 3    |
| 91–100 | 5 | 3   | 3    |

V\* = 3, p\_low = 90, p\_high = 100, clearing price = (90+100)/2 = **95**

D(90) = 5 > S(90) = 3 → buy side rationed. Pool: P0 (qty=5), total = 5.
Pro-rata: P0 = floor(5×3/5) = 3. Leftover = 0.

**Result:** price = 95, traded = 3, fills: P0 = 3 ✓

---

## Scenario 2: No trade — bids below all asks

**Orders:**

| Party | Side | Price | Qty |
|-------|------|-------|-----|
| P0    | Bid  | 85    | 10  |
| P1    | Bid  | 80    | 5   |
| P2    | Ask  | 120   | 8   |

**Hand computation:**

All prices: max bid = 85, min ask = 120. No overlap.
D(p) × S(p) = 0 for all p. V\* = 0.

**Result:** no trade ✓

---

## Scenario 3: Plateau — midpoint tie-break

**Orders:**

| Party | Side | Price | Qty |
|-------|------|-------|-----|
| P0    | Bid  | 105   | 6   |
| P1    | Ask  | 95    | 4   |
| P2    | Ask  | 100   | 3   |

**Hand computation:**

| p     | D(p) | S(p) | V(p)        |
|-------|------|------|-------------|
| 95–99 | 6    | 4    | 4           |
| 100   | 6    | 7    | **6** ← new best |
| 101–105 | 6  | 7    | 6 (plateau) |

V\* = 6, p\_low = 100, p\_high = 105, clearing price = (100+105)/2 = **102.5**

D(100) = 6 < S(100) = 7 → sell side rationed.
Pool: P1 (ap=95, q=4), P2 (ap=100, q=3), total = 7.

| Order    | floor(q×6/7) | Fill |
|----------|-------------|------|
| P1 (q=4) | floor(24/7) = 3 | 3+1 (leftover) = **4** |
| P2 (q=3) | floor(18/7) = 2 | **2** |

Assigned = 5, leftover = 1 → first eligible order (P1) gets +1.

**Result:** price = 102.5, traded = 6, fills: P1 = 4, P2 = 2 ✓

---

## Scenario 4: Pro-rata with leftover (Section 2.4 example)

**Orders:**

| Party | Side | Price | Qty |
|-------|------|-------|-----|
| P0    | Bid  | 110   | 3   |
| P1    | Bid  | 110   | 5   |
| P2    | Bid  | 110   | 2   |
| P2    | Ask  | 100   | 8   |

**Hand computation:**

| p       | D(p) | S(p) | V(p) |
|---------|------|------|------|
| 100–110 | 10   | 8    | 8    |

V\* = 8, p\_low = 100, p\_high = 110, clearing price = (100+110)/2 = **105**

D(100) = 10 > S(100) = 8 → buy side rationed.
Pool: P0 (q=3), P1 (q=5), P2 (q=2), total = 10.

| Order    | floor(q×8/10) | Fill |
|----------|--------------|------|
| P0 (q=3) | floor(24/10) = 2 | 2+1 (leftover) = **3** |
| P1 (q=5) | floor(40/10) = 4 | **4** |
| P2 (q=2) | floor(16/10) = 1 | **1** |

Assigned = 7, leftover = 1 → first eligible order (P0) gets +1.

**Result:** price = 105, traded = 8, fills: P0 = 3, P1 = 4, P2 = 1 ✓
**(Matches PROJECT-STATEMENT.txt Section 2.4 example exactly)**

---

## Scenario 5: Same price — all orders at price 100

**Orders:**

| Party | Side | Price | Qty |
|-------|------|-------|-----|
| P0    | Bid  | 100   | 4   |
| P0    | Ask  | 100   | 4   |
| P1    | Bid  | 100   | 3   |
| P1    | Ask  | 100   | 3   |
| P2    | Bid  | 100   | 5   |
| P2    | Ask  | 100   | 5   |

**Hand computation:**

p = 100: D = 12, S = 12, V = 12. Only relevant price.

V\* = 12, p\_low = p\_high = 100, clearing price = **100**

D(100) = 12 = S(100) = 12 → D not > S → sell side rationed.
Pool: all asks, total = 12. Pro-rata: each gets exact share (no leftover).

| Order    | floor(q×12/12) | Fill |
|----------|---------------|------|
| P0 (q=4) | 4 | **4** |
| P1 (q=3) | 3 | **3** |
| P2 (q=5) | 5 | **5** |

**Result:** price = 100, traded = 12, fills: P0 = 4, P1 = 3, P2 = 5 ✓

---

## Scenario 6: Inactive party — P2 has no orders

**Orders:**

| Party | Side | Price | Qty |
|-------|------|-------|-----|
| P0    | Bid  | 100   | 4   |
| P0    | Ask  | 95    | 2   |
| P1    | Bid  | 105   | 3   |
| P1    | Ask  | 90    | 5   |
| P2    | —    | —     | —   |

**Hand computation:**

| p     | D(p)           | S(p)           | V(p) |
|-------|----------------|----------------|------|
| 90    | 7 (100+105≥90) | 5 (90≤90)      | 5    |
| 91–94 | 7              | 5              | 5    |
| 95    | 7              | 7 (90+95≤95)   | **7** |
| 96–100| 7              | 7              | 7    |
| 101–104| 3             | 7              | 3    |
| 105   | 3              | 7              | 3    |

V\* = 7, p\_low = 95, p\_high = 100, clearing price = (95+100)/2 = **97.5**

D(95) = 7 = S(95) = 7 → sell side rationed.
Pool: P1 (ap=90, q=5), P0 (ap=95, q=2), total = 7.

| Order    | floor(q×7/7) | Fill |
|----------|-------------|------|
| P0 (q=2) | 2 | **2** |
| P1 (q=5) | 5 | **5** |

**Result:** price = 97.5, traded = 7, fills: P0 = 2, P1 = 5, P2 = 0 ✓

---

## Scenario 7: Multiple orders per party

**Orders:**

| Party | Order | Side | Price | Qty |
|-------|-------|------|-------|-----|
| P0    | 0     | Bid  | 100   | 2   |
| P0    | 1     | Bid  | 95    | 3   |
| P1    | 0     | Ask  | 90    | 4   |
| P1    | 1     | Ask  | 100   | 2   |
| P2    | 0     | Bid  | 98    | 1   |

**Hand computation:**

| p   | D(p)                               | S(p)         | V(p) |
|-----|------------------------------------|--------------|------|
| 90  | 6 (100:2 + 95:3 + 98:1)           | 4 (90≤90)    | 4    |
| 91–95 | 6                                | 4            | 4    |
| 96  | 3 (100:2 + 98:1)                  | 4            | 3    |
| 97  | 3                                  | 4            | 3    |
| 98  | 3                                  | 4            | 3    |
| 99  | 2 (100:2)                          | 4            | 2    |
| 100 | 2                                  | 6 (90:4+100:2)| 2   |

V\* = 4, p\_low = 90, p\_high = 95, clearing price = (90+95)/2 = **92.5**

D(90) = 6 > S(90) = 4 → buy side rationed.
Pool: P0o0 (bp=100, q=2), P0o1 (bp=95, q=3), P2o0 (bp=98, q=1), total = 6.

| Order       | floor(q×4/6)    | Fill |
|-------------|----------------|------|
| P0 o0 (q=2) | floor(8/6) = 1 | 1+1 (leftover) = **2** |
| P0 o1 (q=3) | floor(12/6) = 2| **2** |
| P2 o0 (q=1) | floor(4/6) = 0 | **0** |

Assigned = 3, leftover = 1 → P0 o0 gets +1.

**Result:** price = 92.5, traded = 4, fills: P0 = 4 (2+2), P2 = 0 ✓

---

## Scenario 8: Sell side rationed — supply exceeds demand

**Orders:**

| Party | Side | Price | Qty |
|-------|------|-------|-----|
| P0    | Bid  | 105   | 3   |
| P1    | Ask  | 95    | 5   |
| P2    | Ask  | 98    | 4   |

**Hand computation:**

| p     | D(p) | S(p) | V(p) |
|-------|------|------|------|
| 95    | 3    | 5    | 3    |
| 96–97 | 3    | 5    | 3    |
| 98    | 3    | 9    | 3    |
| 99–105| 3    | 9    | 3    |

V\* = 3, p\_low = 95, p\_high = 105, clearing price = (95+105)/2 = **100**

D(95) = 3 < S(95) = 5 → sell side rationed.
Eligible asks at p\_low=95: P1 (ap=95≤95, q=5). P2 (ap=98≤95? NO).
Pool: P1 only, total = 5.

Pro-rata: P1 = floor(5×3/5) = 3. Leftover = 0.

**Result:** price = 100, traded = 3, fills: P1 = 3, P2 = 0 ✓

---

## Summary

| # | Scenario | Price | Traded | Fills | Key feature tested |
|---|----------|-------|--------|-------|--------------------|
| 1 | Basic overlap | 95 | 3 | P0=3 | Simple matching |
| 2 | No trade | — | 0 | — | No overlap |
| 3 | Plateau midpoint | 102.5 | 6 | P1=4, P2=2 | Midpoint tie-break |
| 4 | Pro-rata leftover | 105 | 8 | P0=3, P1=4, P2=1 | Section 2.4 example |
| 5 | Same price | 100 | 12 | P0=4, P1=3, P2=5 | D=S balanced |
| 6 | Inactive party | 97.5 | 7 | P0=2, P1=5 | P2 absent |
| 7 | Multiple orders | 92.5 | 4 | P0=4 | Per-order pro-rata |
| 8 | Sell rationed | 100 | 3 | P1=3 | Sell side rationed |

All 8 scenarios: **hand computation matches simulator output** ✓

**How to run:**
```bash
python3 -B simulator/dark_auction_sim.py --inputs tests/scenarios/scenario_4_prorata_leftover --n-orders 2 --assets 3
```

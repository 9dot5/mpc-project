# Demo Script: Dark Auction Milestone 2

## Pre-Demo Checklist

- [ ] **Docker running**: `docker compose up -d --build party0 party1 party2`
- [ ] **Inputs generated**: `python3 scripts/generate_inputs.py --n-orders 10 --seed 42`
- [ ] **Program compiled**: `docker compose exec party0 bash -c 'cd /mp-spdz && python3 compile.py dark_auction'`
- [ ] **Simulator tested**: `python3 -B simulator/dark_auction_sim.py --inputs Inputs --n-orders 10 --assets 3 --verbose`
- [ ] **Edge cases passing**: `python3 -B tests/edge_cases.py` -> 7/7 PASS

---

## Demo Flow (25–30 minutes)

### 1️⃣ Show Input Files (2 min)
```bash
head -20 inputs/party0.txt
head -20 inputs/party1.txt
```

**Say**: "Party 0 has 10 orders per asset. Each order: bid_price, bid_qty, ask_price, ask_qty. ALL values (prices AND quantities) are read as secrets at runtime via `sint.get_input_from()`. The MPC program uses a fixed price ladder to avoid any dynamic operations on secret data."

---

### 2️⃣ Run Simulator Verbose (3 min)
```bash
python3 simulator/dark_auction_sim.py \
  --inputs Inputs \
  --n-orders 10 \
  --assets 3 \
  --verbose
```

**Say**: "Watch the output. For each asset, you'll see the clearing price (midpoint), traded volume, and per-party fills. The clear-text simulator can show intermediate curves; the MPC program only prints final outputs."

---

### 3️⃣ Compile MPC Program (2–3 min)
```bash
docker compose exec party0 bash -c \
  'cp -f /workspace/dark_auction.mpc /mp-spdz/Programs/Source/dark_auction.mpc && \
   cd /mp-spdz && python3 compile.py dark_auction'
```

**Say**: "The compiler converts MPC code to bytecode. It reads the input files at compile-time to know the price structure, then generates the circuit for the runtime."

---

### 4️⃣ Run MPC Program with MASCOT (3–5 min)
```bash
# Run all 3 parties (each in separate terminal, or use run_auction.sh)
docker compose exec party0 bash -c 'cd /mp-spdz && ./mascot-party.x -N 3 -p 0 -ip Config/IPs -IF Inputs/Input dark_auction'
docker compose exec party1 bash -c 'cd /mp-spdz && ./mascot-party.x -N 3 -p 1 -ip Config/IPs -IF Inputs/Input dark_auction'
docker compose exec party2 bash -c 'cd /mp-spdz && ./mascot-party.x -N 3 -p 2 -ip Config/IPs -IF Inputs/Input dark_auction'
```

**Say**: "MASCOT is a maliciously secure protocol — even if a party deviates from the protocol, it will be detected. All order data stays secret throughout — no intermediate values are revealed. Only the final clearing price, volume, and per-party fills are opened at the end."

---

### 5️⃣ Compare Outputs (1 min)
```bash
# MPC output should match simulator output exactly
diff <(grep "Asset\|Party" mpc_output.txt) <(python3 -B simulator/dark_auction_sim.py --inputs Inputs --n-orders 10 --assets 3)
```

**Say**: "Perfect match—MPC output equals simulator. Correctness verified."

---

### 6️⃣ Run Edge Case Tests (1–2 min)
```bash
python3 -B tests/edge_cases.py
```

**Say**: "5 edge cases — all passing. No-match, single order each side, plateau, equal pro-rata, and one party with no orders."

---

## Anticipated Q&A

### Q: Do you reveal any intermediate values (D(p), S(p))?

**A**: No. The refactored implementation keeps ALL intermediate values as `sint` (secret integers). D(p), S(p), V(p), p_low, p_high, rationed side, and pro-rata shares are all computed in secret arithmetic. Only the final result (clearing price, volume, per-party fills) is revealed via `.reveal()`.

### Q: What does the adversary learn?

**A**: Only the final auction output: clearing price per asset, total traded volume, and each party's aggregate fill. Individual order prices, quantities, and per-order allocations remain completely secret. Even colluding parties cannot reconstruct the third party's orders from the output alone.

### Q: What's the computational cost of keeping everything secret?

**A**: After optimization, the main costs per asset are: (1) scanning 46 price levels × 30 orders = ~2,500 secret comparisons (down from ~25,000 with naive 201-level ladder), (2) 30 sint/sint divisions for per-order pro-rata allocation. Five optimizations yield ~10× fewer comparisons. The 30 divisions per asset remain the dominant cost (~50-100× a multiplication each).

### Q: What optimizations did you apply?

**A**: Five optimizations: (OPT-1) Per-asset price ranges [80,125], [180,225], [30,75] — 46 levels vs 201. (OPT-2) Remove redundant (bp > 0) checks. (OPT-4) Merge Steps C+D. (OPT-5) Precompute (ap > 0) once per asset. (OPT-7) Single-pass eligibility — eliminates 60 sint>=sint comparisons per asset. Combined: ~10× fewer comparisons.

### Q: What if two parties collude?

**A**: Since no intermediate aggregates are revealed, colluding parties only see the final fills (same as any party). They cannot subtract their contribution from D(p)/S(p) because those curves are never opened. The only attack vector is inference from the final output, which is minimal.

### Q: Why pro-rata allocation?

**A**: Fair treatment—each order on rationed side receives proportional share of V*. Simpler than price-priority in MPC (requires tracking arrival times).

### Q: Can you scale to more parties/orders/assets?

**A**: 
- **Parties**: Yes, O(n) cost scaling
- **Orders**: Yes, tested to N_ORDERS=10; more increases unique prices and computation
- **Assets**: Yes, outer loop per asset

Bottleneck: number of unique prices.

### Q: How do you handle the "no-trade" case?

**A**: If best_V == 0 (no bid ≥ any ask), print "Asset X: no trade" and skip allocation. Code explicitly checks this edge case.

### Q: What's the midpoint rule?

**A**: Clearing price = (p_low + p_high) / 2. Ensures fairness—doesn't favor buyers (lower) or sellers (higher). Standard in auction theory.

### Q: How does the fixed price ladder work?

**A**: The program iterates over a public range [30, 230] one price level at a time. At each level `p`, it uses secret comparisons (`bp >= p`, `ap <= p`) to compute D(p) and S(p) as secret integers. The prices in the input ARE secret — they're compared against public ladder values using MPC comparison operators that produce secret bits. No information about actual bid/ask prices leaks from the ladder scan.

### Q: Can you show the pro-rata logic?

**A**: Each order i on rationed side gets: `share_i = (q_i * V*) // total_pool`. Leftover units from floor division distributed round-robin to first eligible orders. Ensures exact total = V* without fractional arithmetic.

---

## Code Pointers

**dark_auction.mpc** (260 lines, optimized):
- Lines 1–36: Header — strict MPC compliance rules, input format, privacy guarantee, optimization list
- Lines 38–68: Phase 1 — Read ALL inputs as secrets via `sint.get_input_from()`
- Lines 70–90: OPT-5 — Precompute `(ap > 0)` bits once per asset
- Lines 92–145: Step A — Per-asset price ladder scan (OPT-1: 46 levels vs 201, OPT-2: no `bp>0`)
- Lines 147–155: Step B — Clearing price = (p_low + p_high) / 2 (secret)
- Lines 157–222: Steps C+D merged (OPT-4) — Rationed side + pro-rata with `sint/sint` division
- Lines 224–245: Step E — Leftover distribution via secret prefix rank
- Lines 247–259: Step F — ONLY `.reveal()` point (final results)

**tests/edge_cases.py**:
- 7 test cases (no-match, single-order, plateau, pro-rata, inactive party, multi-order, N=10 regression)
- Uses tempfile for isolation; validates price, volume, and fills

**simulator/dark_auction_sim.py**:
- `simulate_one_asset()`: Core clearing logic
- `--verbose` flag: Shows D(p), S(p), rationed side, pro-rata details

---

## Timing

| Section | Time |
|---------|------|
| Show inputs | 2 min |
| Simulator verbose | 3 min |
| Compile | 2–3 min |
| Run MPC | 3–5 min |
| Compare | 1 min |
| Tests | 1–2 min |
| **Demo subtotal** | ~15–17 min |
| Q&A (8–10 questions) | 10–15 min |
| **Total** | ~25–30 min |

---

## Pro Tips

1. **Backup ready**: Pre-compile program on backup machine
2. **Screenshot outputs**: Capture key results beforehand
3. **Know the code**: Be ready to open dark_auction.mpc and point out key sections
4. **Practice**: Run through demo 2–3 times beforehand
5. **Print Q&A**: Have these answers on a notecard for reference

---

**Status**: READY FOR DEMO ✓

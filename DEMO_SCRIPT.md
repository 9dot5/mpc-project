# Demo Script: Dark Auction Milestone 2

## Pre-Demo Checklist

- [ ] **Docker running**: `docker compose up -d --build party0 party1 party2`
- [ ] **Inputs generated**: `python3 scripts/generate_inputs.py --n-orders 10 --seed 42`
- [ ] **Program compiled**: `docker compose exec party0 bash -c 'cd /mp-spdz && python3 compile.py dark_auction'`
- [ ] **Simulator tested**: `python3 -B simulator/dark_auction_sim.py --inputs Inputs --n-orders 10 --assets 3 --verbose`
- [ ] **Edge cases passing**: `python3 -B tests/edge_cases.py` -> 5/5 PASS

---

## Demo Flow (25–30 minutes)

### 1️⃣ Show Input Files (2 min)
```bash
head -20 inputs/party0.txt
head -20 inputs/party1.txt
```

**Say**: "Party 0 has 10 orders per asset. Each order: bid_price, bid_qty, ask_price, ask_qty. Prices are public (you can see them), quantities are secret (only MPC sees them)."

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

**Say**: "MASCOT is a maliciously secure protocol — even if a party deviates from the protocol, it will be detected. Each party's quantities stay secret; only aggregates and final fills are revealed."

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

### Q: Why reveal D(p) and S(p)?

**A**: Required to compute V(p) = min(D,S) publicly and find the clearing price interval. Secret comparisons would cost 20–30× more. The trade-off: adversary learns coarse demand/supply distribution, but not individual quantities.

### Q: What does adversary learn from revealed aggregates?

**A**: 
- Which prices have high/low buyer/seller interest
- Order of magnitude of quantities (indirectly, from pro-rata shares)
- Exact individual quantities: NOT revealed

Cannot learn: which party bid what, exact order sizes.

### Q: How would you make it fully private?

**A**: Use secret bitonic sort + selection to compute p_low, p_high without revealing D(p), S(p). Cost: ~O(n² log n) comparisons instead of O(n) reveals. Trade-off: computation vs. communication.

### Q: What if two parties collude?

**A**: They can subtract their own contribution from D(p), S(p) to estimate the third party's orders. Mitigation: secure aggregation (never reveal curves) or differential privacy noise.

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

### Q: Why are prices public?

**A**: Prices define order structure—they're not secret inputs. They're compile-time constants. Quantities (secret) are paired with prices (public) to create orders.

### Q: Can you show the pro-rata logic?

**A**: Each order i on rationed side gets: `share_i = (q_i * V*) // total_pool`. Leftover units from floor division distributed round-robin to first eligible orders. Ensures exact total = V* without fractional arithmetic.

---

## Code Pointers

**dark_auction.mpc**:
- Lines 1–48: Header with algorithm description and privacy analysis
- Lines 50–65: Phase 1 — Compile-time price loading
- Lines 67–82: Phase 2 — Runtime secret quantity reading
- Lines 84–110: Phase 3B — D(p)/S(p) computation with .reveal()
- Lines 112–140: Phase 3D-E — Clearing price selection + rationed side
- Lines 142–170: Phase 3F — Pro-rata allocation with leftover distribution
- Lines 172+: Phase 3G — Output

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

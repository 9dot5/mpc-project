#!/usr/bin/env python3
"""Clear-text simulator for the dark auction (used to validate the MPC program).

Reads MP-SPDZ input files `Inputs/Input-P{pid}-0` and computes clearing
price, traded volume and pro-rata fills per party for each asset using the
algorithm specified in PROJECT-STATEMENT.txt.

Usage: python3 simulator/dark_auction_sim.py --inputs Inputs --n-orders 1 --assets 3
"""
import argparse
import os
from collections import defaultdict

def read_inputs(input_dir, nparties, n_assets, n_orders):
    parties = []
    for pid in range(nparties):
        path = os.path.join(input_dir, f"Input-P{pid}-0")
        with open(path, encoding="utf-8") as f:
            raw_vals = [line.strip() for line in f if line.strip()]
        vals = []
        for v in raw_vals:
            if '.' in v:
                raise ValueError("Decimal prices are not supported: found '{}' in {}".format(v, path))
            try:
                vals.append(int(v))
            except ValueError:
                raise ValueError(f"Non-integer input value '{v}' in {path}")

        expected = n_assets * n_orders * 4
        if len(vals) < expected:
            raise ValueError(f"Input {path} has {len(vals)} values, expected {expected}")

        # reshape: for each asset, for each order: bp bq ap aq
        orders = []
        idx = 0
        for a in range(n_assets):
            asset_orders = []
            for o in range(n_orders):
                bp = vals[idx]; bq = int(vals[idx+1]); ap = vals[idx+2]; aq = int(vals[idx+3])
                asset_orders.append((int(bp), bq, int(ap), aq))
                idx += 4
            orders.append(asset_orders)
        parties.append(orders)
    return parties

def simulate_one_asset(bids, asks):
    # bids/asks: list of (price, qty, pid, order_index)
    prices = sorted(set([p for p,_,_,_ in bids] + [p for p,_,_,_ in asks]))
    if not prices:
        return None
    best_V = -1
    best_prices = []
    D_at_p = {}
    S_at_p = {}
    for p in prices:
        D = sum(q for price,q,_,_ in bids if price >= p)
        S = sum(q for price,q,_,_ in asks if price <= p)
        D_at_p[p] = D
        S_at_p[p] = S
        V = D if D < S else S
        if V > best_V:
            best_V = V
            best_prices = [p]
        elif V == best_V:
            best_prices.append(p)

    if best_V <= 0:
        return {'price': None, 'traded': 0, 'fills': {}}

    p_low = min(best_prices)
    p_high = max(best_prices)
    sum_ph = p_low + p_high
    if sum_ph % 2 == 0:
        clearing_price = sum_ph // 2
    else:
        clearing_price = f"{sum_ph//2}.5"

    V_star = best_V
    D_star = D_at_p[p_low]
    S_star = S_at_p[p_low]
    if D_star > S_star:
        rationed = 'buy'
        pool = [(price,q,pid,o) for price,q,pid,o in bids if price >= p_low]
        total_pool = sum(q for _,q,_,_ in pool)
    else:
        rationed = 'sell'
        pool = [(price,q,pid,o) for price,q,pid,o in asks if price <= p_low]
        total_pool = sum(q for _,q,_,_ in pool)

    # Per-ORDER pro-rata (Section 2.4 of PROJECT-STATEMENT.txt):
    #   fill_i = floor(q_i * V* / total_pool)
    # Leftover units go to the first eligible orders (by party, then order).
    # Fills are then aggregated per party for the final output.
    alloc = defaultdict(int)  # (pid, order_idx) -> fill
    assigned = 0
    if total_pool > 0:
        for price, q, pid, o in pool:
            share = (q * V_star) // total_pool
            alloc[(pid, o)] = share
            assigned += share
        leftover = V_star - assigned
        for price, q, pid, o in pool:
            if leftover <= 0:
                break
            if q > 0:
                alloc[(pid, o)] += 1
                leftover -= 1

    # Aggregate per-order fills into per-party fills
    fills = defaultdict(int)
    for (pid, o), fill in alloc.items():
        fills[pid] += fill

    return {'price': clearing_price, 'traded': V_star, 'fills': dict(fills)}
def simulate(parties, n_assets, n_orders):
    nparties = len(parties)
    results = []
    for a in range(n_assets):
        bids = []
        asks = []
        for pid in range(nparties):
            for o in range(n_orders):
                bp,bq,ap,aq = parties[pid][a][o]
                if bp > 0 and bq > 0:
                    bids.append((bp,bq,pid,o))
                if ap > 0 and aq > 0:
                    asks.append((ap,aq,pid,o))
        res = simulate_one_asset(bids, asks)
        results.append(res)
    return results

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--inputs', default='Inputs')
    p.add_argument('--n-parties', type=int, default=3)
    p.add_argument('--n-orders', type=int, default=1)
    p.add_argument('--assets', type=int, default=3)
    args = p.parse_args()

    parties = read_inputs(args.inputs, args.n_parties, args.assets, args.n_orders)
    results = simulate(parties, args.assets, args.n_orders)

    for a,res in enumerate(results):
        if res is None or res['price'] is None:
            print(f"Asset {a}: no trade")
            continue
        print(f"Asset {a}: clearing_price={res['price']}, traded={res['traded']}")
        for pid in range(args.n_parties):
            print(f"  Party {pid} fill={res['fills'].get(pid,0)}")

if __name__ == '__main__':
    main()

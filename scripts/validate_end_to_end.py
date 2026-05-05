#!/usr/bin/env python3
"""End-to-end validator: generate inputs, run simulator, run MPC parties,
and compare outputs (clearing_price, traded, fills) asset-by-asset.

Usage: python3 scripts/validate_end_to_end.py --seed 42 --n-orders 10
"""
import argparse
import subprocess
import sys
import re
from pathlib import Path

repo = Path(__file__).resolve().parent.parent

def run(cmd, timeout=None):
    return subprocess.run(cmd, shell=True, cwd=str(repo), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)


def parse_sim_output(txt):
    res = {}
    lines = [l.rstrip() for l in txt.splitlines() if l.strip()]
    asset = None
    for line in lines:
        if line.startswith('Asset'):
            parts = line.split(':', 1)[1].strip()
            toks = [t.strip() for t in parts.split(',')]
            cp = None; traded = None
            for t in toks:
                if t.startswith('clearing_price='):
                    cp = t.split('=')[1]
                if t.startswith('traded='):
                    traded = t.split('=')[1]
            asset = int(line.split()[1].strip(':'))
            res[asset] = {'clearing_price': cp, 'traded': int(traded) if traded is not None and traded != '' else 0, 'fills':{}}
        elif line.strip().startswith('Party') and asset is not None:
            m = re.match(r"Party\s+(\d+)\s+fill=(\d+)", line.strip())
            if m:
                pid = int(m.group(1)); v = int(m.group(2))
                res[asset]['fills'][pid] = v
    return res


def parse_mpc_output(txt):
    # MPC prints price_low / price_high; compute clearing_price as midpoint string
    res = {}
    lines = [l.rstrip() for l in txt.splitlines() if l.strip()]
    asset = None
    for line in lines:
        if line.startswith('Asset'):
            # Example: Asset 0: price_low=103 price_high=106 traded=15 rationed_buy=1
            m = re.match(r"Asset\s+(\d+):.*price_low=(\d+)\s+price_high=(\d+)\s+traded=(\d+)", line)
            asset = None
            if m:
                asset = int(m.group(1))
                p_low = int(m.group(2)); p_high = int(m.group(3)); traded = int(m.group(4))
                s = p_low + p_high
                if s % 2 == 0:
                    cp = str(s//2)
                else:
                    cp = f"{s//2}.5"
                res[asset] = {'clearing_price': cp, 'traded': traded, 'fills': {}}
        elif line.strip().startswith('Party') and asset is not None:
            m = re.match(r"Party\s+(\d+)\s+fill=(\d+)", line.strip())
            if m:
                pid = int(m.group(1)); v = int(m.group(2))
                res[asset]['fills'][pid] = v
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--n-orders', type=int, default=10)
    p.add_argument('--assets', type=int, default=3)
    args = p.parse_args()

    print(f"Generating inputs (seed={args.seed}, n_orders={args.n_orders})...")
    rc = run(f"{sys.executable} -B scripts/generate_inputs.py --n-orders {args.n_orders} --seed {args.seed}")
    if rc.returncode != 0:
        print("generate_inputs failed:\n", rc.stdout)
        sys.exit(2)
    print(rc.stdout)

    print("Running simulator...")
    sim = run(f"{sys.executable} -B simulator/dark_auction_sim.py --inputs Inputs --n-orders {args.n_orders} --assets {args.assets}")
    if sim.returncode != 0:
        print("Simulator failed:\n", sim.stdout)
        sys.exit(2)
    print(sim.stdout)
    sim_res = parse_sim_output(sim.stdout)

    print("Running MPC parties (docker compose exec)...")
    cmds = []
    for pid in range(3):
        cmd = f'docker compose exec -T -w /mp-spdz party{pid} ./mascot-party.x -N 3 -p {pid} -ip Config/IPs -IF Inputs/Input dark_auction'
        cmds.append(cmd)

    procs = [subprocess.Popen(c, shell=True, cwd=str(repo), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for c in cmds]
    outs = []
    for pproc in procs:
        out_text, _ = pproc.communicate(timeout=180)
        outs.append(out_text)
    combined = '\n'.join(outs)
    print('--- MPC combined output ---')
    print(combined)

    mpc_res = parse_mpc_output(combined)

    # Compare per asset
    all_ok = True
    for a in range(args.assets):
        sim_a = sim_res.get(a)
        mpc_a = mpc_res.get(a)
        if sim_a is None:
            if mpc_a is None:
                print(f"Asset {a}: no trade (both)")
            else:
                print(f"Asset {a}: MISMATCH — simulator no trade, MPC has {mpc_a}")
                all_ok = False
            continue
        if mpc_a is None:
            print(f"Asset {a}: MISMATCH — simulator has {sim_a}, MPC no trade")
            all_ok = False
            continue
        # Compare clearing_price as strings, traded as ints, fills dicts
        if sim_a['clearing_price'] != mpc_a['clearing_price']:
            print(f"Asset {a}: clearing_price MISMATCH — sim={sim_a['clearing_price']} mpc={mpc_a['clearing_price']}")
            all_ok = False
        if sim_a['traded'] != mpc_a['traded']:
            print(f"Asset {a}: traded MISMATCH — sim={sim_a['traded']} mpc={mpc_a['traded']}")
            all_ok = False
        # compare fills for each party
        for pid in range(3):
            sfill = sim_a['fills'].get(pid, 0)
            mfill = mpc_a['fills'].get(pid, 0)
            if sfill != mfill:
                print(f"Asset {a} Party {pid}: fill MISMATCH — sim={sfill} mpc={mfill}")
                all_ok = False
    if all_ok:
        print('\nE2E validation: PASS — MPC matches simulator for all assets')
        sys.exit(0)
    else:
        print('\nE2E validation: FAIL — see mismatches above')
        sys.exit(3)


if __name__ == '__main__':
    main()

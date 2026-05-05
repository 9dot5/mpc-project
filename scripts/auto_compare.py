#!/usr/bin/env python3
"""
Auto-compare harness for dark_auction: generate inputs, run simulator,
and record results in CSV. Optionally can invoke MPC runs (disabled by
default). Intended to be run inside the project workspace (or inside
container via docker compose exec).

Usage examples:
  python3 scripts/auto_compare.py --seeds 123 124 125 --n-orders 5 --assets 3 --out RUNS/compare.csv --no-mpc

"""
import argparse
import csv
import subprocess
from pathlib import Path
import shlex


def run_cmd(cmd, cwd=None):
    proc = subprocess.run(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return proc.returncode, proc.stdout


def generate_inputs(seed, n_orders):
    cmd = f"python3 scripts/generate_inputs.py --n-orders {n_orders} --seed {seed}"
    return run_cmd(cmd)


def run_simulator(n_orders, assets):
    cmd = f"python3 simulator/dark_auction_sim.py --inputs Inputs --n-orders {n_orders} --assets {assets}"
    return run_cmd(cmd)


def parse_sim_output(txt):
    # returns dict asset -> (clearing_price, traded, fills dict)
    res = {}
    lines = [l.rstrip() for l in txt.splitlines() if l.strip()]
    asset = None
    # support named assets (BTC, ETH, SOL) mapping to indices 0,1,2
    named = {'BTC': 0, 'ETH': 1, 'SOL': 2}
    for line in lines:
        # Legacy numeric asset label: 'Asset 0: ...'
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
            res[asset] = {'clearing_price': cp, 'traded': traded, 'fills': {}}
        # Named assets: 'BTC: ...' or 'ETH: no trade'
        elif any(line.startswith(name + ':') for name in named):
            name = line.split(':', 1)[0]
            aidx = named.get(name)
            rest = line.split(':', 1)[1].strip()
            if rest.lower().startswith('no trade'):
                res[aidx] = {'clearing_price': None, 'traded': '0', 'fills': {}}
                asset = aidx
            else:
                toks = [t.strip() for t in rest.split(',')]
                cp = None; traded = None
                for t in toks:
                    if t.startswith('clearing_price='):
                        cp = t.split('=')[1]
                    if t.startswith('traded='):
                        traded = t.split('=')[1]
                res[aidx] = {'clearing_price': cp, 'traded': traded, 'fills': {}}
                asset = aidx
        elif line.strip().startswith('Party') and asset is not None:
            # Party 0 fill=6
            p = int(line.split()[1])
            v = int(line.split('=')[1])
            res[asset]['fills'][p] = v
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--seeds', nargs='+', type=int, required=True)
    p.add_argument('--n-orders', type=int, default=5)
    p.add_argument('--assets', type=int, default=3)
    p.add_argument('--out', default='RUNS/compare.csv')
    p.add_argument('--no-mpc', action='store_true', help='Do not attempt to run MPC parties')
    p.add_argument('--run-mpc', action='store_true', help='Attempt to run MPC parties via docker compose (must be run from host with docker available)')
    args = p.parse_args()

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)

    header = ['seed','asset','sim_clearing_price','sim_traded']
    # dynamic party fill columns: detect parties from Inputs files (assume 3)
    for pid in range(3):
        header.append(f'sim_fill_p{pid}')

    with open(outp, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for seed in args.seeds:
            print(f"=== Seed {seed} ===")
            rc, out = generate_inputs(seed, args.n_orders)
            if rc != 0:
                print(f"generate_inputs failed (seed={seed}):\n{out}")
                continue
            # Run simulator (clear-text)
            rc, sim_out = run_simulator(args.n_orders, args.assets)
            if rc != 0:
                print(f"simulator failed (seed={seed}):\n{sim_out}")
                continue
            parsed = parse_sim_output(sim_out)
            for asset in range(args.assets):
                row = [seed, asset]
                asset_res = parsed.get(asset)
                if asset_res:
                    row.append(asset_res['clearing_price'])
                    row.append(asset_res['traded'])
                    for pid in range(3):
                        row.append(asset_res['fills'].get(pid, 0))
                else:
                    row.extend(['',''])
                    row.extend([0,0,0])
                writer.writerow(row)
            print(sim_out)

            # Optionally run MPC parties (requires docker compose on the host)
            if args.run_mpc and not args.no_mpc:
                # Check docker availability
                docker_ok = True
                try:
                    check = subprocess.run(['docker','compose','version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if check.returncode != 0:
                        docker_ok = False
                except FileNotFoundError:
                    docker_ok = False

                if not docker_ok:
                    print('Skipping MPC run: "docker compose" not found in this environment. Run the script from the host or install Docker CLI.')
                else:
                    print('Running MPC parties via docker compose...')
                    cmds = []
                    for pid in range(3):
                        cmd = f'docker compose exec party{pid} bash -lc "cd /mp-spdz && ./mascot-party.x -N 3 -p {pid} -ip Config/IPs -IF Inputs/Input \"dark_auction\""'
                        cmds.append(cmd)
                    procs = [subprocess.Popen(c, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for c in cmds]
                    outs = []
                    for pproc in procs:
                        out_text, _ = pproc.communicate()
                        outs.append(out_text)
                    combined = '\n'.join(outs)
                    print('--- MPC combined output ---')
                    print(combined)
                    # naive parse: reuse parse_sim_output on combined output
                    parsed_mpc = parse_sim_output(combined)
                    # Compare parsed and parsed_mpc and print differences (simple)
                    for asset in range(args.assets):
                        sim_r = parsed.get(asset)
                        mpc_r = parsed_mpc.get(asset)
                        if sim_r != mpc_r:
                            print(f'Asset {asset}: MISMATCH between simulator and MPC')
                        else:
                            print(f'Asset {asset}: OK (sim == mpc)')

    print(f"Wrote results to {outp}")


if __name__ == '__main__':
    main()

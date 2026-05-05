#!/usr/bin/env python3
"""Run N_ORDERS=10 regression (uses repo's generator + simulator).
This script generates inputs with seed 42 and compares simulator output
against the expected results embedded in tests/edge_cases.py.
"""
import subprocess
import sys
from pathlib import Path
from simulator.dark_auction_sim import read_inputs, simulate

repo_root = Path(__file__).parent.parent
python = sys.executable

print("Generating inputs (n_orders=10, seed=42)...")
proc = subprocess.run([python, '-B', 'scripts/generate_inputs.py', '--n-orders', '10', '--seed', '42'], cwd=str(repo_root))
if proc.returncode != 0:
    print("Generator failed (exit code", proc.returncode, ")")
    sys.exit(2)

input_dir = str(repo_root / 'Inputs')
print("Reading generated Inputs from", input_dir)
parties = read_inputs(input_dir, 3, 3, 10)
results = simulate(parties, 3, 10)

expected = [
    {'price': "104.5", 'traded': 15, 'fills': {0: 10, 1: 3, 2: 2}},
    {'price': 202, 'traded': 15, 'fills': {0: 6, 1: 4, 2: 5}},
    {'price': "52.5", 'traded': 15, 'fills': {0: 3, 1: 9, 2: 3}},
]

all_pass = True
for a in range(3):
    res = results[a]
    exp = expected[a]
    ok = (res['price'] == exp['price'] and res['traded'] == exp['traded'] and res['fills'] == exp['fills'])
    print(f"Asset {a}: expected={exp}, got={res}, ok={ok}")
    if not ok:
        all_pass = False

if all_pass:
    print("N_ORDERS=10 regression: PASS")
    sys.exit(0)
else:
    print("N_ORDERS=10 regression: FAIL")
    sys.exit(1)

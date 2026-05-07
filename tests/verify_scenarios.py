#!/usr/bin/env python3
"""Verify all hand-computed scenarios against the simulator.

Usage: python3 -B tests/verify_scenarios.py
"""
import sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from simulator.dark_auction_sim import simulate, read_inputs

EXPECTED = {
    'scenario_1_basic_overlap': [
        {'price': 95, 'traded': 3, 'fills': {0: 3}},
        None, None,
    ],
    'scenario_2_no_trade': [None, None, None],
    'scenario_3_plateau_midpoint': [
        {'price': '102.5', 'traded': 6, 'fills': {1: 4, 2: 2}},
        None, None,
    ],
    'scenario_4_prorata_leftover': [
        {'price': 105, 'traded': 8, 'fills': {0: 3, 1: 4, 2: 1}},
        None, None,
    ],
    'scenario_5_same_price': [
        {'price': 100, 'traded': 12, 'fills': {0: 4, 1: 3, 2: 5}},
        None, None,
    ],
    'scenario_6_inactive_party': [
        {'price': '97.5', 'traded': 7, 'fills': {0: 2, 1: 5}},
        None, None,
    ],
    'scenario_7_multi_orders': [
        {'price': '92.5', 'traded': 4, 'fills': {0: 4}},
        None, None,
    ],
    'scenario_8_sell_rationed': [
        {'price': 100, 'traded': 3, 'fills': {1: 3}},
        None, None,
    ],
}

def main():
    base = Path(__file__).parent / 'scenarios'
    passed = failed = 0

    print("=" * 60)
    print("HAND-VERIFIED SCENARIO VALIDATION")
    print("=" * 60)

    for name in sorted(EXPECTED.keys()):
        d = str(base / name)
        if not os.path.isdir(d):
            print(f"  [SKIP] {name} (directory not found)")
            continue

        results = simulate(read_inputs(d, 3, 3, 2), 3, 2)
        exp = EXPECTED[name]
        ok = True

        for a in range(3):
            r = results[a]
            e = exp[a]
            if e is None:
                if r is not None and r['price'] is not None:
                    print(f"    Asset {a}: expected no trade, got {r}")
                    ok = False
            else:
                if r is None or r['price'] is None:
                    print(f"    Asset {a}: expected {e}, got no trade")
                    ok = False
                elif r['price'] != e['price'] or r['traded'] != e['traded']:
                    print(f"    Asset {a}: price/traded mismatch: got {r}")
                    ok = False
                else:
                    for pid in range(3):
                        if r['fills'].get(pid, 0) != e['fills'].get(pid, 0):
                            print(f"    Asset {a} P{pid}: fill {r['fills'].get(pid,0)} != {e['fills'].get(pid,0)}")
                            ok = False

        if ok:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name}")

    print()
    print("=" * 60)
    total = passed + failed
    print(f"RESULT: {passed}/{total} passed" +
          (" — ALL OK" if failed == 0 else f" — {failed} FAILED"))
    print("=" * 60)
    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)

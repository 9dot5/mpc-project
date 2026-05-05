#!/usr/bin/env python3
"""
Edge-case and regression tests for the dark auction simulator.

Validates correctness of the clearing price algorithm, pro-rata allocation,
and edge cases before running on the MPC framework.

Usage: python3 -B tests/edge_cases.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from simulator.dark_auction_sim import simulate, read_inputs


class TestCase:
    """Represents a single test case with expected outputs."""

    def __init__(self, name, n_parties=3, n_assets=3, n_orders=1):
        self.name = name
        self.n_parties = n_parties
        self.n_assets = n_assets
        self.n_orders = n_orders
        self.parties = [[[None for _ in range(n_orders)] for _ in range(n_assets)]
                        for _ in range(n_parties)]
        self.expected_results = [None for _ in range(n_assets)]

    def set_order(self, pid, asset, order_idx, bp, bq, ap, aq):
        self.parties[pid][asset][order_idx] = (bp, bq, ap, aq)

    def fill_zeros(self):
        """Fill any unset orders with zeros."""
        for pid in range(self.n_parties):
            for a in range(self.n_assets):
                for o in range(self.n_orders):
                    if self.parties[pid][a][o] is None:
                        self.parties[pid][a][o] = (0, 0, 0, 0)

    def set_expected(self, asset, price, traded, fills):
        self.expected_results[asset] = {'price': price, 'traded': traded, 'fills': fills}

    def write_inputs(self, input_dir):
        self.fill_zeros()
        for pid in range(self.n_parties):
            path = os.path.join(input_dir, f"Input-P{pid}-0")
            with open(path, "w") as f:
                for asset in range(self.n_assets):
                    for o in range(self.n_orders):
                        bp, bq, ap, aq = self.parties[pid][asset][o]
                        f.write(f"{bp}\n{bq}\n{ap}\n{aq}\n")

    def run(self):
        """Run test case and return (passed, details)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self.write_inputs(tmpdir)
            results = simulate(
                read_inputs(tmpdir, self.n_parties, self.n_assets, self.n_orders),
                self.n_assets, self.n_orders
            )
            return self._check(results)

    def _check(self, results):
        all_pass = True
        details = []
        for asset in range(self.n_assets):
            result = results[asset]
            expected = self.expected_results[asset]
            if result is None:
                result = {'price': None, 'traded': 0, 'fills': {}}

            ok = (result['price'] == expected['price'] and
                  result['traded'] == expected['traded'] and
                  result['fills'] == expected['fills'])
            if not ok:
                all_pass = False
                details.append(f"  Asset {asset}: expected {expected}, got {result}")
        return all_pass, details


# =============================================================================
# TEST DEFINITIONS
# =============================================================================

def test_no_match():
    """All bids below all asks — no trade should occur."""
    tc = TestCase("No match (bids < asks)")
    for pid in range(3):
        tc.set_order(pid, 0, 0, 80, 5, 120, 3)
        tc.set_order(pid, 1, 0, 50, 4, 150, 2)
        tc.set_order(pid, 2, 0, 30, 3, 200, 4)
    tc.set_expected(0, None, 0, {})
    tc.set_expected(1, None, 0, {})
    tc.set_expected(2, None, 0, {})
    return tc


def test_single_order_each_side():
    """One bid and one ask from same party, overlapping prices."""
    tc = TestCase("Single order each side (bid=100, ask=95)")
    tc.set_order(0, 0, 0, 100, 5, 95, 3)  # bid at 100 qty 5, ask at 95 qty 3
    # Other parties/assets empty
    for a in range(3):
        tc.set_expected(a, "97.5" if a == 0 else None,
                       3 if a == 0 else 0,
                       {0: 3} if a == 0 else {})
    return tc


def test_plateau_balanced():
    """All parties bid and ask at same price, same qty — p_low == p_high."""
    tc = TestCase("Plateau (all same price=100, qty=10)")
    for pid in range(3):
        for a in range(3):
            tc.set_order(pid, a, 0, 100, 10, 100, 10)
    for a in range(3):
        tc.set_expected(a, 100, 30, {0: 10, 1: 10, 2: 10})
    return tc


def test_pro_rata_unequal():
    """Unequal quantities on rationed side — verify floor + leftover."""
    tc = TestCase("Pro-rata with leftover", n_orders=2)
    # Asset 0: 3 buyers compete, seller has 8 units
    # Buyers: P0 has qty 3, P1 has qty 5, P2 has qty 2 (total=10, V*=8)
    # shares: floor(3*8/10)=2, floor(5*8/10)=4, floor(2*8/10)=1 → assigned=7, leftover=1→P0
    tc.set_order(0, 0, 0, 110, 3, 0, 0)
    tc.set_order(1, 0, 0, 110, 5, 0, 0)
    tc.set_order(2, 0, 0, 110, 2, 100, 8)
    # Assets 1,2 no orders
    tc.set_expected(0, 105, 8, {0: 3, 1: 4, 2: 1})
    tc.set_expected(1, None, 0, {})
    tc.set_expected(2, None, 0, {})
    return tc


def test_one_party_inactive():
    """Party 2 submits no orders (all zeros) — auction still works."""
    tc = TestCase("One party inactive (P2 = zeros)")
    tc.set_order(0, 0, 0, 100, 4, 95, 2)
    tc.set_order(1, 0, 0, 105, 5, 90, 3)
    # P2 all zeros (fill_zeros handles it)
    # Bids: P0@100 qty4, P1@105 qty5. Asks: P0@95 qty2, P1@90 qty3.
    # Prices: 90, 95, 100, 105
    # D(90)=9, S(90)=3 → V=3
    # D(95)=9, S(95)=5 → V=5
    # D(100)=9, S(100)=5 → V=5
    # D(105)=5, S(105)=5 → V=5
    # best_V=5, p_low=95, p_high=105, clearing=(95+105)/2=100
    # D(95)=9 > S(95)=5 → buy rationed
    # Eligible buys (bid>=95): P0@100 qty4, P1@105 qty5 → pool=9
    # shares: floor(4*5/9)=2, floor(5*5/9)=2 → assigned=4, leftover=1→P0
    tc.set_expected(0, 100, 5, {0: 3, 1: 2})
    tc.set_expected(1, None, 0, {})
    tc.set_expected(2, None, 0, {})
    return tc


def test_multiple_orders_per_party():
    """N_ORDERS=3, multiple orders from each party at different prices."""
    tc = TestCase("Multiple orders (N_ORDERS=3)", n_orders=3)
    # Asset 0 only, simple scenario
    # P0: bid@100 qty2, bid@95 qty3, ask@90 qty1
    tc.set_order(0, 0, 0, 100, 2, 0, 0)
    tc.set_order(0, 0, 1, 95, 3, 0, 0)
    tc.set_order(0, 0, 2, 0, 0, 90, 1)
    # P1: ask@95 qty4, ask@100 qty2
    tc.set_order(1, 0, 0, 0, 0, 95, 4)
    tc.set_order(1, 0, 1, 0, 0, 100, 2)
    # P2: bid@98 qty1
    tc.set_order(2, 0, 0, 98, 1, 0, 0)
    # Prices: 90, 95, 98, 100
    # D(90)=6, S(90)=1 → V=1
    # D(95)=6, S(95)=5 → V=5
    # D(98)=3, S(98)=5 → V=3
    # D(100)=2, S(100)=7 → V=2
    # best_V=5 at p=95. p_low=p_high=95, clearing=95
    # D(95)=6 > S(95)=5 → buy rationed
    # Eligible buys (bid>=95): P0o0@100 q2, P0o1@95 q3, P2o0@98 q1 → pool=6
    # shares: floor(2*5/6)=1, floor(3*5/6)=2, floor(1*5/6)=0 → assigned=3, leftover=2→P0o0,P0o1
    tc.set_expected(0, 95, 5, {0: 5, 2: 0})
    tc.set_expected(1, None, 0, {})
    tc.set_expected(2, None, 0, {})
    return tc


def test_n_orders_10_random():
    """N_ORDERS=10 with seed 42 — regression test against known output."""
    import subprocess
    # Generate inputs with seed 42
    proc = subprocess.run(
        ['python3', '-B', 'scripts/generate_inputs.py', '--n-orders', '10', '--seed', '42'],
        capture_output=True, text=True, cwd=str(Path(__file__).parent.parent)
    )
    if proc.returncode != 0:
        return None  # skip if generator not available

    tc = TestCase("N_ORDERS=10 seed=42 regression", n_orders=10)
    # Read from generated files and run
    input_dir = str(Path(__file__).parent.parent / "Inputs")
    parties = read_inputs(input_dir, 3, 3, 10)
    results = simulate(parties, 3, 10)

    # Known expected results for seed 42 N_ORDERS=10
    expected = [
        {'price': "104.5", 'traded': 15, 'fills': {0: 10, 1: 3, 2: 2}},
        {'price': 202, 'traded': 15, 'fills': {0: 6, 1: 4, 2: 5}},
        {'price': "52.5", 'traded': 15, 'fills': {0: 3, 1: 9, 2: 3}},
    ]

    all_pass = True
    details = []
    for a in range(3):
        res = results[a]
        exp = expected[a]
        ok = (res['price'] == exp['price'] and
              res['traded'] == exp['traded'] and
              res['fills'] == exp['fills'])
        if not ok:
            all_pass = False
            details.append(f"  Asset {a}: expected {exp}, got {res}")
    return all_pass, details


# =============================================================================
# TEST RUNNER
# =============================================================================

def run_tests():
    tests = [
        test_no_match(),
        test_single_order_each_side(),
        test_plateau_balanced(),
        test_pro_rata_unequal(),
        test_one_party_inactive(),
        test_multiple_orders_per_party(),
    ]

    passed = 0
    failed = 0

    print("=" * 70)
    print("DARK AUCTION — EDGE CASE TEST SUITE")
    print("=" * 70)

    for tc in tests:
        ok, details = tc.run()
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {tc.name}")
        if not ok:
            for d in details:
                print(d)
            failed += 1
        else:
            passed += 1

    # Special test: N_ORDERS=10 regression
    print()
    print("  [....] N_ORDERS=10 seed=42 regression", end="")
    result = test_n_orders_10_random()
    if result is None:
        print("\r  [SKIP] N_ORDERS=10 seed=42 regression (generator unavailable)")
    else:
        ok, details = result
        status = "PASS" if ok else "FAIL"
        print(f"\r  [{status}] N_ORDERS=10 seed=42 regression")
        if not ok:
            for d in details:
                print(d)
            failed += 1
        else:
            passed += 1

    print()
    print("=" * 70)
    total = passed + failed
    print(f"RESULT: {passed}/{total} passed" + (" — ALL OK" if failed == 0 else f" — {failed} FAILED"))
    print("=" * 70)
    return failed == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)

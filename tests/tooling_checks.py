#!/usr/bin/env python3
"""Targeted checks for tooling regressions around parsing and input validation."""

import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.auto_compare import parse_sim_output
from simulator.dark_auction_sim import read_inputs

TMP_ROOT = Path(__file__).parent / ".tmp"
TMP_ROOT.mkdir(exist_ok=True)


def make_case_dir(name: str) -> Path:
    path = TMP_ROOT / f"{name}_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_parse_named_assets():
    sample = """BTC: clearing_price=97.5, traded=3
  Party 0 fill=3
  Party 1 fill=0
ETH: no trade
SOL: clearing_price=150, traded=5
  Party 2 fill=5
"""
    parsed = parse_sim_output(sample)
    assert parsed[0]["clearing_price"] == "97.5"
    assert parsed[0]["traded"] == "3"
    assert parsed[0]["fills"] == {0: 3, 1: 0}
    assert parsed[1]["clearing_price"] is None
    assert parsed[1]["traded"] == "0"
    assert parsed[2]["fills"] == {2: 5}


def test_parse_legacy_asset_labels():
    sample = """Asset 0: clearing_price=98, traded=6
  Party 0 fill=6
"""
    parsed = parse_sim_output(sample)
    assert parsed[0]["clearing_price"] == "98"
    assert parsed[0]["traded"] == "6"
    assert parsed[0]["fills"] == {0: 6}


def test_decimal_price_inputs_fail_fast():
    tmpdir = make_case_dir("decimal_price_inputs")
    path = os.path.join(tmpdir, "Input-P0-0")
    with open(path, "w", encoding="utf-8") as f:
        f.write("100.50\n2\n90\n1\n")
    for pid in (1, 2):
        with open(os.path.join(tmpdir, f"Input-P{pid}-0"), "w", encoding="utf-8") as f:
            f.write("100\n2\n90\n1\n")

    try:
        read_inputs(str(tmpdir), nparties=3, n_assets=1, n_orders=1)
    except ValueError as exc:
        assert "Decimal prices are not supported" in str(exc)
    else:
        raise AssertionError("Expected decimal price inputs to be rejected")


def main():
    test_parse_named_assets()
    test_parse_legacy_asset_labels()
    test_decimal_price_inputs_fail_fast()
    print("tooling_checks.py: all checks passed")


if __name__ == "__main__":
    main()

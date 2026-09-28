#!/usr/bin/env python3
"""
business_agent.py - STUB, not wired into anything yet.

The idea (see PRICE-DISCOVERY.md's Phase 4): given a lot, assess whether
it's a plausible input to a small business - resale inventory, a flip, or
tooling that could start/supply a side business. "10 industrial sewing
machines" reads differently to someone weighing an alterations business
than "1 sewing machine" does; that's the kind of signal this is meant to
surface, on top of (not instead of) the existing deal/valuation pipeline.

Deliberately not called from auction_finder.py or auction_value.py yet.
A wrong price estimate costs a bad bid; a wrong "this could be a
business" read risks steering someone toward a real bet on a business
idea - a different, higher failure cost that needs a real design (what
counts as a business angle, how confident is confident enough to surface
at all, what the UI even looks like) before this does anything but
return None.
"""


def evaluate_business_potential(lot):
    """Stub. Will eventually return something like
    {"angle": str, "confidence": float, "note": str} for a lot worth
    surfacing as a small-business opportunity, or None for everything
    else - not implemented, always returns None for now."""
    return None


if __name__ == "__main__":
    print("business_agent.py is a stub - see PRICE-DISCOVERY.md Phase 4. "
          "evaluate_business_potential() always returns None right now.")

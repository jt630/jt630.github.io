"""Musick Auction's buyer-side fees, so a bid can be shown as what you'd
actually pay. Source: the "Auction Fees" block on every lot page's Terms tab
(captured 2026-10-07, tests/fixtures/musick_lot_detail_wrangler.html):

    Buyer's Premium: 10% for all purchases equal to or greater than $10,000.
    There will be an additional 5% for all purchases of $9,999 or less.
    PER LOT.  Vehicle Doc Fees: $150 in-state.  Firearm Fee: $15 per firearm.

READING OF THE AMBIGUOUS SENTENCE: sub-$10k purchases pay 10% + 5% = 15%;
$10k and up pay 10%. If Musick says otherwise, change PREMIUM_* below - this
is the only place it lives. Idaho sales tax / title fees are NOT included
(vehicle tax is paid at the DMV, not to the auction).
"""

PREMIUM_BASE = 0.10
PREMIUM_SMALL_SURCHARGE = 0.05      # purchases of $9,999 or less
SURCHARGE_BELOW = 10_000
VEHICLE_DOC_FEE = 150               # in-state buyer
FIREARM_FEE = 15


def premium_rate(price):
    return PREMIUM_BASE + (PREMIUM_SMALL_SURCHARGE if price < SURCHARGE_BELOW else 0.0)


def all_in(price, category=None):
    """Total cost of winning at `price` (hammer): price + buyer's premium +
    the per-lot doc/firearm fee. None if there's no price."""
    if not isinstance(price, (int, float)) or price <= 0:
        return None
    total = price * (1 + premium_rate(price))
    if category == "Vehicles":
        total += VEHICLE_DOC_FEE
    elif category == "Firearms":
        total += FIREARM_FEE
    return round(total)


def max_bid_for_budget(budget, category=None):
    """Highest hammer price whose all-in cost stays within `budget`."""
    if not isinstance(budget, (int, float)) or budget <= 0:
        return None
    lo, hi = 0, int(budget)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if all_in(mid, category) <= budget:
            lo = mid
        else:
            hi = mid - 1
    return lo or None

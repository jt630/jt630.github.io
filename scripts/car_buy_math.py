"""
Car buying math: new vs used, Boise ID, Sept 2026.
Target: Subaru Forester (or non-CVT alternative). 7-year hold.

All dollar inputs are point estimates with a band noted in comments.
Run: python scripts/car_buy_math.py
"""

def loan(principal, apr, months):
    r = apr / 12
    if r == 0:
        pmt = principal / months
    else:
        pmt = principal * r / (1 - (1 + r) ** -months)
    total_paid = pmt * months
    interest = total_paid - principal
    return pmt, total_paid, interest

# ---- shared assumptions ----
IDAHO_SALES_TAX = 0.06          # Ada County, no local add-on
DOC_FEE = 500                   # ID dealer doc fee, ~$300-500
HOLD_YEARS = 7
DOWN = 4000                     # cash down, same for both scenarios
MILES_PER_YEAR = 12000

# Rates: "higher for longer" view. Sept 2026.
APR_NEW = 0.072                 # 0.069-0.079 band, captive/credit-union new
APR_USED = 0.089               # 0.084-0.099 band, used 3-6 yr old
APR_BUYER = 0.0499             # Jeremy's pre-approval: used-car loan, up to
                               # $100k, 65 mo, 4.99% fixed APR (secured, no
                               # variable-rate risk). Terms below kept < 65 mo
                               # deliberately -- pay it faster, no prepay
                               # penalty, build equity sooner.

# Annual costs that DIFFER by age
def insurance(age_of_car_start):
    # newer car = higher comp/collision premium; rough Boise full-coverage
    base = 1450
    return base - min(age_of_car_start, 6) * 55   # ~$55/yr less per year older

def maintenance(model_year_age):
    # Subaru CVT-era: cheap first 3 yrs, climbs after warranty (36k b2b / 60k powertrain)
    if model_year_age <= 3: return 350
    if model_year_age <= 6: return 750
    return 1150

GAS_PER_GAL = 3.60             # Boise regular, higher-oil view; 3.40-3.90 band

# Manufacturer captive-APR offers, Boise, Sept 2026. SECONDARY-sourced
# (subaru.com / buyatoyota.com PNW via search snippets); confirm with a Boise
# ZIP before relying on them. No customer/bonus cash on any of the 3 models.
#   Subaru Forester (gas): 1.9% / 36 mo, $0 down, exp ~9/30/2026
#   Toyota RAV4 / 4Runner: ~4.99% / 48 mo
#   Subaru CPO Forester (2021-2026): ~4.29% (this line is PRIMARY off subaru.com)
APR_FORESTER_PROMO = 0.019
APR_TOYOTA_PROMO = 0.0499
APR_SUBARU_CPO = 0.0429

SCENARIOS = {
    "NEW 2026 Forester Premium": {
        "price": 33200,            # 31.5k-35k OTD-negotiated pre-tax; MSRP ~33-35k
        "apr": APR_NEW,
        "term": 72,
        "start_age": 0,
        "mpg": 28,
        # resale after 7 yrs / ~84k mi: Subaru holds ~ well
        "resale": 15500,           # 14k-17k band -> ~47% of price
    },
    "NEW 2026 Forester Premium -- 1.9% promo (36mo)": {
        "price": 33200,
        "apr": APR_FORESTER_PROMO,
        "term": 36,                # headline rate REQUIRES the 36-mo term
        "start_age": 0,
        "mpg": 28,
        "resale": 15500,
    },
    "NEW 2026 Forester Premium -- 3.9% est. (60mo)": {
        "price": 33200,
        "apr": 0.039,              # SOFT: Subaru 48/60-mo rate not published; est. band 3.4-4.9%
        "term": 60,
        "start_age": 0,
        "mpg": 28,
        "resale": 15500,
    },
    "USED 2023 Forester (~30k mi)": {
        "price": 26500,
        "apr": APR_USED,
        "term": 60,
        "start_age": 3,
        "mpg": 28,
        "resale": 12500,           # 10yr-old car at sale, ~11k-14k
    },
    "CPO 2023 Forester (~30k mi) -- Subaru 4.29%": {
        "price": 28000,            # CPO carries ~$1.5k premium over private used
        "apr": APR_SUBARU_CPO,
        "term": 60,
        "start_age": 3,
        "mpg": 28,
        "resale": 13000,           # slightly better resale w/ CPO history
    },
    "USED 2023 Forester (~30k mi) -- your 4.99% line": {
        "price": 26500,
        "apr": APR_BUYER,
        "term": 60,
        "start_age": 3,
        "mpg": 28,
        "resale": 12500,
    },
    "USED 2020 Forester (~65k mi) -- your 4.99% line": {
        "price": 20500,
        "apr": APR_BUYER,
        "term": 48,
        "start_age": 6,
        "mpg": 27,
        "resale": 8500,
    },
    "USED 2020 Forester (~65k mi)": {
        "price": 20500,            # 19k-22.5k
        "apr": APR_USED,
        "term": 48,
        "start_age": 6,
        "mpg": 27,
        "resale": 8500,            # 13yr-old car, 145k mi
    },
    "USED 2023 Toyota RAV4 (8-sp auto, NO CVT, ~35k mi)": {
        "price": 29000,            # RAV4 commands ~2-3k premium over Forester
        "apr": APR_USED,
        "term": 60,
        "start_age": 3,
        "mpg": 28,
        "resale": 15000,           # RAV4 resale is class-leading
    },
    "USED 2019 Toyota 4Runner SR5 4WD (8-sp auto, NO CVT, ~70k mi)": {
        "price": 33000,            # 31k-36k; 4Runners barely depreciate
        "apr": APR_USED,
        "term": 60,
        "start_age": 7,
        "mpg": 17,
        "resale": 22000,           # legendary resale, still 20k+ at 14yo/155k
    },
    "USED 2021 Honda Passport EX-L AWD (9-sp auto, NO CVT, ~50k mi)": {
        "price": 28000,            # 26k-30k
        "apr": APR_USED,
        "term": 60,
        "start_age": 5,
        "mpg": 21,
        "resale": 14500,
    },
}

print(f"{'scenario':52} {'OTD':>8} {'fin':>8} {'pmt/mo':>8} {'interest':>9} "
      f"{'ins7yr':>8} {'maint7yr':>9} {'depr':>8} {'fuel7yr':>8} {'7yr TCO':>9} {'$/mo all-in':>12}")
print("-" * 145)

for name, s in SCENARIOS.items():
    otd = s["price"] * (1 + IDAHO_SALES_TAX) + DOC_FEE
    financed = max(otd - DOWN, 0)
    pmt, total_paid, interest = loan(financed, s["apr"], s["term"])

    ins = sum(insurance(s["start_age"] + y) for y in range(HOLD_YEARS))
    mnt = sum(maintenance(s["start_age"] + y) for y in range(HOLD_YEARS))
    depr = s["price"] - s["resale"]
    fuel = MILES_PER_YEAR * HOLD_YEARS / s["mpg"] * GAS_PER_GAL

    # 7-yr total cost of ownership = depreciation + interest + insurance + maint
    tco = depr + interest + ins + mnt + fuel
    per_mo = tco / (HOLD_YEARS * 12)

    print(f"{name:52} {otd:8.0f} {financed:8.0f} {pmt:8.0f} {interest:9.0f} "
          f"{ins:8.0f} {mnt:9.0f} {depr:8.0f} {fuel:8.0f} {tco:9.0f} {per_mo:12.0f}")

print()
print("Notes:")
print("- TCO now includes fuel at ${:.2f}/gal, {} mi/yr. Excludes registration (~$140/yr flat, same for all).".format(GAS_PER_GAL, MILES_PER_YEAR))
print("- RAV4 Hybrid (~39 mpg) would cut the RAV4 fuel line ~$4,600 over 7 yrs -> best-in-table TCO.")
print("- 'depr' is price - resale; the NEW car's first-year drop (~20%) is the single biggest line.")
print("- Forester has NO non-CVT option in any year 2014+. RAV4 / 4Runner / Passport are the non-CVT alternatives.")
print("- 2019+ Subaru CVT (TR580/690) is materially better than 2014-18; extended warranty history on the older ones.")

# ---- emit data/car_math.yaml so the site table re-derives from this script ----
import datetime, json, pathlib
rows = []
for name, s in SCENARIOS.items():
    otd = s["price"] * (1 + IDAHO_SALES_TAX) + DOC_FEE
    financed = max(otd - DOWN, 0)
    pmt, total_paid, interest = loan(financed, s["apr"], s["term"])
    ins = sum(insurance(s["start_age"] + y) for y in range(HOLD_YEARS))
    mnt = sum(maintenance(s["start_age"] + y) for y in range(HOLD_YEARS))
    depr = s["price"] - s["resale"]
    fuel = MILES_PER_YEAR * HOLD_YEARS / s["mpg"] * GAS_PER_GAL
    tco = depr + interest + ins + mnt + fuel
    rows.append({
        "name": name, "otd": round(otd), "financed": round(financed),
        "pmt_mo": round(pmt), "interest": round(interest), "insurance": round(ins),
        "maintenance": round(mnt), "fuel": round(fuel), "depreciation": round(depr),
        "tco_7yr": round(tco), "per_mo_allin": round(tco / (HOLD_YEARS * 12)),
    })
out = {
    "generated": datetime.date.today().isoformat(),
    "assumptions": {
        "hold_years": HOLD_YEARS, "miles_per_year": MILES_PER_YEAR, "down": DOWN,
        "apr_new": APR_NEW, "apr_used": APR_USED, "idaho_sales_tax": IDAHO_SALES_TAX,
        "doc_fee": DOC_FEE, "gas_per_gal": GAS_PER_GAL,
    },
    "scenarios": rows,
}
# minimal YAML writer (avoid adding pyyaml dep)
def to_yaml(obj, indent=0):
    pad = "  " * indent
    lines = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{pad}{k}:")
                lines.append(to_yaml(v, indent + 1))
            else:
                lines.append(f"{pad}{k}: {json.dumps(v)}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                first = True
                for k, v in item.items():
                    prefix = f"{pad}- " if first else f"{pad}  "
                    lines.append(f"{prefix}{k}: {json.dumps(v)}")
                    first = False
            else:
                lines.append(f"{pad}- {json.dumps(item)}")
    return "\n".join(lines)
pathlib.Path("data/car_math.yaml").write_text(to_yaml(out) + "\n")
print("\nwrote data/car_math.yaml")

#!/usr/bin/env python3
"""One-off: patch deal_rating / market_delta into the cars.com cache files from
data gathered via WebFetch on 2026-09-01 (cars.com results + detail pages).
Keyed by vehicledetail UUID. Safe to re-run."""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(_HERE, "..", "data", ".cache")

# uuid -> (deal_rating, market_delta)   (None where cars.com showed no rating)
ENRICH = {
    # forester
    "cc00fd36-67c2-4b5f-85f1-d5f526354485": ("Great Deal", -700),
    "fa6f1def-ac96-4b01-b9e3-4a6370e36ebe": ("Good Deal", None),
    "59574cc6-75a3-4a0f-824a-c01c8ae8ac70": ("Good Deal", None),
    "c3aa5820-a3a6-4220-a4cb-be08109e6303": (None, None),
    "1bccde9b-3866-4dbd-893e-81532b6dac8e": ("Good Deal", None),
    "63e04d14-7cac-4ecf-ac40-d15040101098": ("Good Deal", None),
    "3e432680-eaed-499c-a751-887e6ae6ff50": ("Good Deal", -491),
    "94f87236-496d-4528-b0be-402d88e9a384": ("Good Deal", -346),
    "cb9948ab-617e-450d-aa7c-79f15ceb93ac": (None, -493),
    "078b4294-dbe9-4677-8e63-342830f3c4cb": ("Fair Price", None),
    "156433e3-6dd7-4680-9106-ea1f970fedc6": ("Good Deal", None),
    "5a4e68d1-5bbb-4e74-ae25-f316beff5436": (None, None),
    "fe9043f8-1ce0-4ec2-bffe-165665d86e1a": ("Good Deal", None),
    "53d99a24-bc71-42b9-bfa2-000b48f3243d": ("Fair Price", None),
    "7bb3e878-ceeb-4234-a623-606cc8a410e1": ("Good Deal", -401),
    "fcef2b75-e63b-4f14-a32a-f3d98ec22e70": ("Fair Price", 1600),
    "e20b6884-1f74-4d35-96b0-23c4f8a3c74c": ("Fair Price", None),
    "f62c1888-5536-4dbf-a6c4-0d4f1a8f63dc": (None, None),
    "9edb1ad1-6aa8-424b-b752-c7750e429bb7": (None, -300),
    "c527cb19-33cd-48b6-83e3-e8096d3b2f5c": ("Good Deal", None),
    "1b763353-50fa-4910-90d2-7e161f4a4293": ("Great Deal", -1907),  # detail page
    "e6562781-57b6-4a65-a3a1-3514e56d97b2": (None, None),
    "dadaf652-5d61-4572-8320-6d66ba31a3df": ("Great Deal", None),
    # fourrunner
    "57a31a60-2435-4858-bb2a-332c0bd5bb1b": ("Great Deal", -899),
    "8a4ff133-c2e2-468c-874a-a0b4834e2c74": ("Good Deal", None),
    "32aa0069-a32f-4f5d-b4f7-9ac24f889aeb": ("Good Deal", None),
    "48fa9a60-63e1-41c0-84a8-c7f26014a238": ("Good Deal", -370),
    "fb5c2432-acdc-4e39-a2c8-b7e0812d5152": ("Good Deal", None),
    "df9fd09b-4334-4021-95c7-7abc3ee95fcf": ("Good Deal", None),
    "ed150a27-eab7-4367-9102-a8f8459cdf5c": ("Good Deal", None),
    "a8f2b111-d173-4780-b961-987515c08ffd": ("Great Deal", -1100),
    "f817377d-1e96-4942-aa55-294a2babd148": ("Good Deal", None),
    "6de47688-c10e-4f23-9a21-14f3e038f2cd": ("Great Deal", None),
    "062bbf01-7ab5-4e9f-b111-11b892c499f9": ("Fair Price", -100),
    "91721e5e-c3c4-4853-9b1e-8567a8a0e0cc": ("Great Deal", -571),
    "f4d237de-1b00-4276-841a-3eb19ad49e3e": ("Great Deal", -700),
    "ea212fb4-0e4f-419b-87b0-ce978e316792": ("Good Deal", None),
    "10c213a0-19c1-49d5-b166-b66f555827bb": ("Good Deal", -100),
    "181db67a-bb85-4a94-9386-21762ca459f0": ("Fair Price", None),
    "4ddbb9ba-cdac-4164-b154-4b7433bb205a": ("Good Deal", None),
    "8ec4a748-7dc8-42c2-83f7-acaee54ee24b": ("Good Deal", None),
    "b1b2fd73-dd8d-4287-b581-b02fb47f17d6": ("Great Deal", -912),  # detail page
    "f9645d6c-f04e-45e2-9281-4eac4e5b5d15": ("Good Deal", -1900),
    "7dce0725-f35c-4563-bd24-85c803337703": ("Good Deal", -1200),
    "7afaae8e-094b-4233-83bc-543d75a70ca4": ("Great Deal", None),
    "ed763ac2-6ff6-4b1b-ba57-d58eb4c4992b": ("Good Deal", None),
    # passport
    "0a5a0aac-28f6-4b28-8b0c-da5a75fc700c": (None, None),
    "21aafb6d-c1c3-4c42-8b47-05bcc477a8af": (None, -400),
    "5b0355d4-4ccb-4531-9a4b-a4a210069338": ("Good Deal", None),
    "31ba27ae-8b24-4c23-9034-aaea7faad010": ("Good Deal", None),
    "15a05b1d-8928-4e6c-9217-c831a18bd95d": ("Good Deal", None),
}

for fn in os.listdir(CACHE):
    if not fn.startswith("carscom_") or not fn.endswith(".json"):
        continue
    path = os.path.join(CACHE, fn)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    hit = 0
    for r in data.get("rows", []):
        uuid = r.get("url", "").rstrip("/").rsplit("/", 1)[-1]
        dr, md = ENRICH.get(uuid, (None, None))
        r["deal_rating"] = dr
        r["market_delta"] = md
        if dr or md:
            hit += 1
    data["deal_data_note"] = ("deal_rating / market_delta captured 2026-09-01 "
                              "from cars.com results + detail pages via WebFetch")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    print(f"{fn}: {hit}/{len(data.get('rows', []))} rows with deal data")

Find campsites for a trip using the recreation.gov API, including the walk-up sites the website hides.

## Why this exists

Recreation.gov's website shows a booking calendar. Much of the Forest Service
inventory in Idaho is first-come, first-served and **never appears in that
calendar**. A campground that looks "sold out" online is routinely half empty
and waiting for walk-ups. This command reads the API directly and separates
"booked" from "not in the booking system."

Full API notes: `docs/RECREATION-API.md`

## Steps

1. Collect from the user, asking only for what they haven't already said:
   - **Where** — a town, a region, or specific campground names
   - **When** — first night, and how many nights
   - **What matters** — hot springs, fishing, swimming, seclusion, berries,
     short drive, showers, etc.
   - **Departure time**, if they mention it. This decides whether walk-up is a
     real strategy: checkout is 11:00 AM, so an early start means arriving into
     fresh turnover.

2. Sweep the region:

   ```bash
   python scripts/campsite_finder.py near --lat LAT --lon LON --radius 50 \
       --start YYYY-MM-DD --nights N --limit 25 \
       --origin "LAT,LON" --max-drive 3.5 --depart "11:00"
   ```

   **Always pass `--origin`.** `--radius` is straight-line miles and is badly
   misleading in mountain country — a campground 35 crow-flies miles away can be
   a 5-hour drive around a wilderness. `--origin` adds routed drive times and
   sorts by them; `--max-drive` hides the ones that are secretly half a day out.

   If drive times come back empty, the public OSRM routing server's certificate
   has expired again. Re-run with `--insecure-routing` (it relaxes TLS for that
   one routing host, never for recreation.gov), or fall back to the ROAD column.

   Prefer explicit `--lat/--lon`; the geocoder behind `--from` is unreliable and
   has resolved town names tens of miles off. Look coordinates up first if the
   user gave a place name.

   For named campgrounds instead:

   ```bash
   python scripts/campsite_finder.py search "warm lake"
   python scripts/campsite_finder.py check 234030 234254 --start YYYY-MM-DD --nights N
   ```

3. **Read the columns correctly.** This is the part that matters:
   - `OPEN` — bookable right now. Book it or lose it.
   - `BOOKED` — genuinely gone.
   - `WALK-UP` — first-come sites, held out of the booking system all month.
     **Never report these as unavailable.** A campground with 0 OPEN and 12
     WALK-UP is a good target for an early Friday arrival, not a dead end.
   - `?` — seasonal or closed. Say so rather than guessing.
   - `DRIVE` — routed driving time. Conservative on mountain highway, so use it
     to rank destinations, not to promise an arrival time.
   - `ROAD` — surface warnings scraped from the agency's own directions text
     (GRAVEL, DIRT, NARROW, STEEP, ROUGH, HIGH-CLEARANCE, 4WD, NO TRAILERS).
     Surface this to the user. It matters a lot for a loaded car, a low-clearance
     vehicle, or a trailer, and it is the difference between a scenic drive and
     two hours of washboard.
   - `SCAN&PAY` — the user pays on arrival through the recreation.gov app and
     needs it downloaded **before** losing service.

4. Check the things the API does not know, and do not skip these:
   - **Fire restrictions.** Search current stage for the counties involved.
     Under Stage 1, wood fires are legal *only* in installed rings at developed
     sites — which means **dispersed camping gets no campfire at all**. This
     changes cooking plans and often the whole destination choice.
   - **Wildfire and smoke** for the dates.
   - **Reservoir drawdown**, if swimming or paddling matters. Late-season
     irrigation reservoirs can be mud and stumps.
   - **Hot springs** nearby, and whether they need reservations.
   - Pull `facility_directions` from the API for the chosen campground — the
     official route often differs from what navigation apps pick, sometimes
     dramatically in road quality.

5. Present **2–4 real options**, scored against the user's stated weights, with
   drive times. State plainly which are bookable now and which need a walk-up
   gamble, and give the odds honestly (how many walk-up sites, what arrival time).

6. Recommend a **belt-and-suspenders plan** when walk-up is involved: book a
   bookable site as insurance, then drive to the better walk-up target first.
   Name the fallback chain in order.

7. Offer to write it up as a dated page in `content/backpacking/`, following the
   pattern in `content/backpacking/car-camping-aug-28-2026.md`. Always date the
   page and state when availability was checked — **this data goes stale in days.**

## Rules

- **Never say "sold out" from `OPEN: 0` alone.** Check the walk-up column first.
  Getting this wrong is the single most likely failure of this command.
- **Never recommend a campground on radius alone.** Get the routed drive time and
  the road warnings before putting it in front of the user. "Close on the map" and
  "reachable" are different things once mountains are involved.
- Always print the date the availability was checked. Numbers move fast.
- If the user names a campground, check it even if you think it's full — they
  usually know something about the place worth confirming.
- Cite sources for anything not from the API (fire restrictions, hot springs
  hours, road conditions).

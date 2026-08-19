# Recreation.gov API — field notes

Undocumented but stable JSON API behind recreation.gov. **No key, no auth.** Send a
browser `User-Agent` or you may get blocked.

Written 2026-08-18 while planning the Aug 28–30 trip. The tooling built on it is
[`scripts/campsite_finder.py`](../scripts/campsite_finder.py), driven by `/campsites`.

## Why bother

The recreation.gov website shows a **booking calendar**. A large share of Forest
Service inventory — often *most* of it in the Idaho backcountry — is
first-come, first-served and **never appears in that calendar at all**. Read the
site casually and you conclude a campground is full when half of it is sitting
empty waiting for walk-ups.

This API exposes the distinction. That's the entire reason to use it.

---

## Base

```
https://www.recreation.gov/api
```

Required header:

```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...
```

Rate limiting is not published. Sleep ~0.4s between calls.

---

## Endpoints

### 1. Search — find facility IDs

```
GET /search?q=warm+lake&entity_type=campground&size=10
GET /search?lat=44.91&lng=-116.10&radius=50&entity_type=campground&size=25
```

`radius` is in **miles**. Returns `results[]`, each with:

| Field | Meaning |
|---|---|
| `entity_id` | **the facility ID** — the key to everything else |
| `name`, `city`, `state_code` | labels |
| `campsites_count` | total sites (string) |
| `latitude` / `longitude` | for further radius searches |
| `reservable` | whether the facility is in the booking system *at all* |
| `aggregate_cell_coverage` | rough cell signal, 0–4ish. Useful. |

The lat/lng form is the powerful one: it sweeps a whole region rather than
guessing names.

### 2. Facility detail

```
GET /camps/campgrounds/{facility_id}
```

Returns `campground` with `facility_name`, `facility_description`,
`facility_directions` (**the official route — often differs from what map apps
suggest**), and `facility_rules` (`maxStay`, `reservationCutOff`).

`facility_directions` is underrated. For Deadwood Reservoir it specifies the
maintained FR 579 approach via Lowman, not the beat-up FS 555 track that
navigation apps route you onto.

### 3. Campsite metadata

```
GET /camps/campgrounds/{facility_id}/campsites
```

Returns `campsites[]`. Key fields:

| Field | Meaning |
|---|---|
| `campsite_id` | joins to the availability response |
| `campsite_name` | the site number you'd see on a post |
| `campsite_type` | `STANDARD NONELECTRIC`, `WALK TO`, `GROUP STANDARD NONELECTRIC`, `MANAGEMENT` |
| `site_details_map` | `campfire_allowed`, `checkin_time`, `max_num_people`, `pets_allowed`, … |
| `permitted_equipment` | tent / RV / trailer with max lengths |

**`campsite_type: MANAGEMENT` with a name like "Scan and Pay Single"** is the tell
that the campground accepts walk-ups paid on arrival by QR code through the
recreation.gov mobile app. It's a strong signal there is real first-come inventory.

### 4. Availability — the important one

```
GET /camps/availability/campground/{facility_id}/month?start_date=2026-08-01T00%3A00%3A00.000Z
```

`start_date` **must be the first of a month**, URL-encoded, `.000Z` on the end.
One month per call; a trip spanning a month boundary needs two calls.

```jsonc
{
  "campsites": {
    "10160542": {
      "campsite_id": "10160542",
      "site": "009",
      "availabilities": {
        "2026-08-28T00:00:00Z": "Reserved",
        "2026-08-29T00:00:00Z": "Reserved"
      }
    }
  }
}
```

Date keys are `YYYY-MM-DDT00:00:00Z` — note **no milliseconds here**, unlike the
`start_date` parameter. Easy to get wrong.

---

## Reading the status values

This is the whole game.

| Value | Means |
|---|---|
| `Available` | bookable right now |
| `Reserved` | someone booked it — genuinely gone |
| `Not Reservable` | **not in the booking system** |

`Not Reservable` is doing a lot of work and **is not a synonym for full.** It covers:

1. **First-come, first-served sites** — held out of the system on purpose.
2. Sites closed for the season, or a season not yet released.
3. Sites out of service for maintenance.

### Telling them apart

Check the **whole month**, not just your dates:

- `Not Reservable` on **every day of the month** → walk-up inventory (or closed).
- A mix of `Not Reservable` and `Reserved`/`Available` → seasonal release boundary.

Corroborate walk-up status with:
- a `MANAGEMENT` / "Scan and Pay" campsite in the metadata,
- the phrase "Scan and Pay" or "first-come" in `facility_description`.

### Worked example — Upper Payette Lake (`234030`)

19 standard sites, Aug 28–29 2026:

- 8 sites `Reserved` — the reservable half, genuinely booked
- **10 sites `Not Reservable` every day in August — first-come**
- 2 `MANAGEMENT` "Scan and Pay" entries confirming walk-up payment

Read only the booking calendar and this campground looks sold out. In fact
**more than half of it is walk-up** and it never enters the calendar.

The same pattern is everywhere in the Payette and Boise national forests —
Last Chance (21 walk-up), Yellow Pine (14), Hazard Lake (11), Buckhorn Bar (10),
Ice Hole (10), Ponderosa (10), Golden Gate (9), Poverty Flat (8). Several of
these are **100% walk-up** — zero reservable sites, so they are invisible to
anyone browsing the booking calendar.

---

## Gotchas

- **`start_date` must be the 1st of a month.** Arbitrary dates return junk.
- **Millisecond mismatch:** `.000Z` in the request, plain `T00:00:00Z` in response keys.
- **Group and management sites** inflate counts. Filter on `campsite_type` before
  totalling anything.
- **A night is the check-in date.** Two nights starting Aug 28 = keys for Aug 28
  *and* Aug 29. Off-by-one here silently produces wrong answers.
- **`/search/geocoder` is unreliable.** `"McCall, ID"` resolved ~40 mi east of
  McCall. Prefer explicit `--lat/--lon` when precision matters.
- **Facility IDs are not all numeric** — some are UUIDs. Treat them as strings.
- **404 on facility detail** happens for forest-level entities (e.g. `1025`
  "Payette National Forest"), which are not campgrounds. Skip them.

---

## Beyond camping

`entity_type` also accepts `permits`, `tours`, `recarea`, and `activitypass`,
which is the path to river permits and lottery-style bookings. Unexplored here.

## Related

- [`scripts/campsite_finder.py`](../scripts/campsite_finder.py) — the wrapper
- `/campsites` — the slash command that drives it
- [Trip plan: Aug 28–30, 2026](../content/backpacking/car-camping-aug-28-2026.md) — where this came from

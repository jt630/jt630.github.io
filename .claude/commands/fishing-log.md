Ingest fishing trips the owner logged on /fishing/ and use them to tune the rating.

The owner pastes YAML copied from the page's "Copy new trips as YAML" button (or a
`fishing-export.json`). Entries look like:

```
- id: "202610091530-sf-boise-dam"
  when: "2026-10-09T15:30"
  spot: "sf-boise-dam"
  field: {water_f, air_f, clarity, wading, bugs, worked, caught, biggest_in, rating (1-5), notes}
  predicted: {score, band, confidence}     # what the page said at save time
  conditions: {flow_cfs, flow_pct24, water_f, water_src, air_f, cloud, wind_mph, pop, pressure_hpa, pressure_delta6}
```

Steps:

1. Parse the pasted entries. Skip any whose `id` is already in `data/fishing_log.yaml`.
2. Append the new ones under `trips:` in `data/fishing_log.yaml`, unchanged. Never edit
   `predicted` or `conditions`: they are the page's record at the time (same rule as
   the THESIS.md predictions).
3. Compare, per entry, `predicted.score` against `field.rating`. A 4-5 rating on a
   Skip/Tough prediction, or 1-2 on Prime/Good, is a miss. Say which factor was probably
   wrong (flow range, water temp curve, wind, pressure, etc.).
4. Where `field.water_f` was measured at a spot with `water_src` = "seasonal estimate",
   compare it to the month's value in `water_f_by_month` in `data/fishing.yaml`.
5. Only propose tuning changes in `data/fishing.yaml` (flow ranges, `water_f_by_month`,
   `trout_temp_f`, `weights`, `score_curve`, tactics text). With fewer than ~5 trips,
   do not change numbers: say what the data hints at and wait. With more, make small
   changes and explain each one.
6. Run `hugo --minify`, then commit on a feature branch and open a PR per CLAUDE.md.

Also explain to the owner what you changed and why, since the point of the log is to
teach them how the rating gets better.

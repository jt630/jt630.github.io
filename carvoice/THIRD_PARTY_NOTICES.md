# CarVoice — Third-Party Notices

CarVoice adapts code and data from **speed785/open-mechanic**
(https://github.com/speed785/open-mechanic), MIT-licensed. See
`carvoice/research/open-mechanic-review.md` for the review that led to
reusing it instead of writing the same plumbing from scratch.

## What was taken

- `data/carvoice/dtc_codes.json` — vendored verbatim from open-mechanic's
  `data/dtc_codes.json` (522 DTC codes with description/severity/category).
- `scripts/carvoice/obd2_logger.py` — `OBDConnection`, sensor-snapshot
  reading, and DTC reading are adapted from open-mechanic's
  `src/open_mechanic/connection.py`, `reader.py`, and `dtc.py`.
- `scripts/carvoice/diagnose.py` — the diagnostic system prompt, JSON output
  schema, and disclaimer-injection pattern are adapted from open-mechanic's
  `src/open_mechanic/ai/prompts.py` and `ai/diagnose.py`.

Each adapted file carries a short attribution note pointing back here.

## open-mechanic's license

```
MIT License

Copyright (c) 2026 open-mechanic contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## CarVoice's own license

CarVoice's own code will be released under MIT too (per `CARVOICE.md` Status),
which is compatible with the above.

# daily-page

The morning fetcher for The Daily Page (Brief Deck). Every day at about 5am NZ time,
`fetch.py` collects a dozen fragments from public sources (NYT feeds, the V&A, Wellcome
Collection, the Met, and one festival synopsis from `festivals.json`), crops each by a fixed
rule, and saves them to `found/YYYY-MM-DD.js`. No AI is involved at any step.

Run it by hand from the Actions tab ("morning" → Run workflow).

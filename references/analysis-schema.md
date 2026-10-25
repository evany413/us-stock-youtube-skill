# Concise Analysis Data Contract

After reviewing the complete transcript and relevant screenshots, write `analysis.json` in the run directory. This structured file is the template source for both reports. Keep every summary and outlook to one sentence.

Use schema version 2:

```json
{
  "schema_version": 2,
  "video": {
    "date": "2026-10-24",
    "youtuber": "Example Channel",
    "title": "Example market update",
    "url": "https://www.youtube.com/watch?v=VIDEO_ID"
  },
  "current_events": [
    {
      "topic": "Fed and major earnings",
      "summary": "A dense event calendar may increase market volatility next week."
    }
  ],
  "market": {
    "stance": "mixed",
    "summary": "Liquidity is tight, but the major indices have not confirmed a breakdown.",
    "outlook": "Watch the stated index support and upcoming earnings for direction."
  },
  "stocks": [
    {
      "ticker": "SPY",
      "company": "SPDR S&P 500 ETF",
      "stance": "mixed",
      "action": "watch",
      "key_levels": "759–776 strong support; a break turns bearish",
      "outlook": "A loss of the first support zone would open more downside."
    }
  ],
  "note": "Transcript came from ASR, so some proper nouns may be uncertain."
}
```

## Allowed values

- `stance`: `bullish`, `bearish`, `neutral`, `mixed`, or `not-stated`.
- `action`: `buy`, `hold`, `sell`, `watch`, `avoid`, or `not-stated`.

## Concision rules

- Combine related news into 3–5 `current_events`; each `summary` is one sentence and contains only the most decision-relevant effect.
- `market.summary` states the present condition. `market.outlook` states the next key catalyst or condition. Do not repeat the same point in both.
- Each stock gets one row. Do not add separate bullish/bearish reason lists or timecodes.
- `key_levels` is one compact line containing only decision-relevant levels and conditions, for example `759–776 強支撐，跌破偏空；728–753 下一支撐`. Do not prefix every range with redundant wording such as `支撐點位`.
- Use an empty string for `key_levels` when the video provides no useful level.
- `outlook` is one short sentence and should absorb the essential reason only when it changes the conclusion.

## Evidence rules

- `video.date` is the publication date when available; use `YYYY-MM-DD` or `unknown`.
- Consolidate repeated discussion of one ticker into one stock object.
- Record an action only when the speaker explicitly states or clearly describes it; otherwise use `not-stated`.
- Record levels only when stated or legible in reviewed evidence. Preserve essential conditions and horizons, but do not calculate missing levels.
- Keep speaker claims separate from external facts. Do not update an old video's view using current prices.
- Use an empty event or stock array when no supported item exists. Do not invent content to fill the report.

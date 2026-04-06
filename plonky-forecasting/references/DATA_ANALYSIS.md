# Pre-Forecast Data Analysis

Before configuring the forecast, inspect the data for patterns that affect model quality. You can do this by examining the uploaded data or asking the user about it. This step is optional for simple datasets but strongly recommended for anything non-trivial.

## Outliers

Look for extreme values that could pull the forecast off track.

- **Spikes**: A single day with 10x normal volume is probably Black Friday or a data error — ask the user which.
- **Drops to zero**: Revenue going to zero for a week could be a system outage, a holiday closure, or missing data. The model will treat it as a real signal either way.
- **Rule of thumb**: Any value more than 3x the median for its period deserves a question to the user. Don't silently let it through.
- **What to do**: If it's a data error, ask the user to fix and re-upload. If it's a real but non-recurring event (warehouse fire, one-time promotion), warn the user that the model may over- or under-weight it.

## Concentration

When the dataset has dimensions (region, product, channel), check how volume is distributed.

- **Top-heavy data**: If one segment has 60% of total volume and the bottom 10 segments share 5%, the small segments will produce noisy, unreliable forecasts. Tell the user: "The bottom segments have very little data — forecasts for those will be rough estimates at best."
- **Single-segment dominance**: If one dimension value is >80% of the total, a dimension-level forecast may not add much value over an aggregate forecast. Suggest running aggregate first.
- **Minimum viable segment size**: Segments with fewer than 30 data points will produce wide confidence intervals. Flag these before spending credits on them.

## Trend and Regime Changes

Check whether the recent data looks fundamentally different from the historical pattern.

- **Recent acceleration or deceleration**: If the last 3 months show a steep change that isn't present in prior data, the model may lag behind reality. Flag it: "Recent growth is much faster than historical — the forecast may be conservative."
- **Structural breaks**: COVID, a product pivot, entering a new market, losing a major customer — any event that makes the pre-event data misleading. If the user confirms a break, suggest forecasting only from post-break data.
- **Plateaus after growth**: A series that grew steadily then flattened may trick the model into projecting continued growth. Note the flattening.

## Sparsity and Intermittency

Some series have long stretches of zero or near-zero values.

- **Intermittent demand**: Common in retail at SKU level or B2B with infrequent large orders. Standard forecasting models struggle with this. Warn the user that confidence intervals will be very wide and point estimates less reliable.
- **Seasonal zeros**: A business that closes in January will have legitimate zeros. Make sure the model sees enough cycles of this pattern (2+ years).

## Data Recency

Check when the data ends relative to today.

- **Stale data**: If the most recent data point is 3+ months old, the forecast starts from an outdated baseline. Tell the user: "Your data ends in [date] — the forecast will project from that point, not from today. If conditions have changed since then, results may be off."
- **Very fresh data**: If the last data point is today or yesterday, check whether it looks like a partial period (e.g., today's revenue at 9am is not a full day). Partial periods at the end of the series can distort the model.

## Summary

After this analysis, give the user a brief honest assessment before proceeding:
- "This data looks clean with a clear trend — good candidate for forecasting."
- "Revenue is heavily concentrated in 2 of 15 regions. I'd recommend forecasting aggregate + top 5 only."
- "There's a sharp break 6 months ago — I'll use only recent data for a more accurate forecast."
- "This data has a lot of zero-value days and high variance. Forecasts will be directional at best."

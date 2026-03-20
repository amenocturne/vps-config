# Weighted average vs AVERAGE()

## Problem
When calculating average prices across countries/products with different volumes,
using `=AVERAGE(prices)` gives a wildly incorrect result.

Example: country A has price 0.01 with volume 500, country B has price 220 with volume 10.
AVERAGE gives 110, but the actual weighted average is 12.1.

## Solution
Always use weighted average: **Total Value / Total Quantity**.

```
= SUMPRODUCT(prices, quantities) / SUM(quantities)
```

Or when working with separate value and quantity columns:
```
= SUM(value_column) / SUM(quantity_column)
```

Never use AVERAGE() or AVERAGEIF() for prices — they treat all rows equally regardless of volume.

## Key insight
AVERAGE() is almost always wrong for prices and rates. If rows represent different volumes,
a small-volume row with an extreme price will distort the result.
The only time AVERAGE is correct is when all rows have equal weight.

# Unit conversion in formulas

## Problem
Data comes in mixed units (kilograms and units/pieces in the same column).
Need to normalize everything to one unit for aggregation.

## Solution
Use a reference cell for the conversion factor, not a hardcoded number.

```
; Put conversion factor in a named cell, e.g., B1 = 50 (kg per unit)
; Then in the formula:
=IF(unit_column="Kilogram", value / $B$1, value)
```

Or when converting kg to tons:
```
=SUMIFS(...) / 1000
```

Rules:
- **Never hardcode constants** (50, 1000, 90) directly in formulas
- Put them in a clearly labeled cell and reference it with `$`
- This makes the model auditable and easy to change

## Key insight
Hardcoded "magic numbers" in formulas are the #1 source of errors in financial models.
If the conversion factor changes (e.g., 50 kg → 45 kg), you'd have to find and update
every formula. A single reference cell fixes all of them at once.

# SUMIFS for multi-criteria filtering

## Problem
Need to sum values from large datasets (e.g., 14,000+ customs declarations) filtered by
multiple criteria: year, month, direction (import/export), product type.

## Solution
SUMIFS with absolute-referenced ranges and relative criteria:

```
=SUMIFS(
  Декларации!$O:$O,        ; sum range (weight) — always $-locked
  Декларации!$C:$C, N$1,   ; criterion 1: year (from header row)
  Декларации!$D:$D, N$2,   ; criterion 2: month (from header row)
  Декларации!$E:$E, $F17,  ; criterion 3: direction (from label column)
  Декларации!$L:$L, $B17   ; criterion 4: product type (from label column)
) / 1000
```

Key rules:
- **Sum range and criteria ranges**: always `$` (absolute) — they don't move when stretching
- **Criteria values**: lock the axis that stays fixed. `N$1` locks row (moves across columns), `$F17` locks column (moves down rows)
- Divide by 1000 for unit conversion (kg → tons) directly in the formula

## Key insight
The `$`-locking pattern is what makes SUMIFS stretchable. Lock ranges fully (`$O:$O`),
lock criteria partially based on which direction the formula will be copied.
Use F4 to cycle: full lock → row only → column only → unlocked.

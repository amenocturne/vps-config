# P&L waterfall with hierarchical aggregation

## Problem
Build a consolidated financial result (P&L) from source data across multiple sheets,
with hierarchical rollups: brand → segment → channel → category → total.

## Solution

### Structure
```
Grand Total (Dogs + Cats)
├── Dogs Total (Online + Offline)
│   ├── Dogs Online
│   │   ├── Economy (10 brands, SUM)
│   │   └── Premium (10 brands, SUM)
│   └── Dogs Offline
│       ├── Economy (10 brands, SUM)
│       └── Premium (10 brands, SUM)
└── Cats Total (same structure)
```

### P&L lines per product per month
```
Revenue       = Volume (tons) × Price (RUB/kg) × 1000
COGS          = Volume (tons) × Cost (RUB/kg) × 1000
Gross Profit  = Revenue - COGS
Gross Margin  = 1 - COGS / Revenue
```

### Formula pattern
- Brand level: `='source_sheet'!C7` (cross-sheet link to source data)
- Segment level: `=SUM(D8:D17)` (10 brands)
- Channel level: `=D6+D29` (economy + premium)
- Category level: `=D5+D53` (online + offline)
- Grand total: `=D4+D100` (dogs + cats)

### Key rules
- Source data stays untouched on separate sheets
- Calculation sheet only contains references and SUM
- Formulas stretch horizontally for months (Jan-Dec)
- Annual total = SUM of monthly cells

## Key insight
The entire 687-row P&L is built with only two formula types: cross-sheet references
and SUM. No VLOOKUP, no IF. Simplicity in formula choice makes the model auditable.
Keep calculated columns separate from source data tables.

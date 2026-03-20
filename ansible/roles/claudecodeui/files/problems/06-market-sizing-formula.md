# Market sizing: Production + Import - Export

## Problem
Calculate total market size for a product category in a country, then determine
company market share.

## Solution

### Market size formula
```
Market Size = Domestic Production + Import - Export
```

In Excel:
```
=D10 + D4 - D7
```
Where D10 = production, D4 = import, D7 = export (all in same units).

### Market share
```
='Продажи Компании'!K22 / D13
```
Company sales divided by total market size.

### Monetary values
For revenue-based market size, multiply volumes by prices:
```
=D10 * Росстат_Цены!C5
```

### Data sources (Russian market context)
- **Production**: Rosstat (Росстат) — by federal district, monthly
- **Import/Export**: Customs declarations (Декларации) — by country, monthly
- **Prices**: Rosstat producer prices or calculated weighted averages from customs data

## Key insight
Always verify that all components use the same units (tons vs kg, USD vs RUB)
and the same time period. A common mistake is mixing annual production with
monthly import data.

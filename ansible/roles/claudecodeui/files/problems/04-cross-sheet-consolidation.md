# Cross-sheet data consolidation

## Problem
Data lives across multiple sheets (e.g., 7 regional production sheets, 4 source data sheets).
Need to build a summary that pulls and aggregates from all of them.

## Solution

### Method 1: Direct cross-sheet references
```
='Росстат_Пр-во ЦФО'!D5 + 'Росстат_Пр-во СЗФО'!D5 + ... + 'Росстат_Пр-во ДФО'!D5
```
Good for a small number of sheets.

### Method 2: SUM across sheet range
```
=SUM('Sheet1:Sheet7'!C5)
```
Sums cell C5 from all sheets between Sheet1 and Sheet7 (inclusive).
Sheets must be contiguous in the workbook tab order.

### Method 3: INDIRECT for dynamic references
```
=IFERROR(INDIRECT(ADDRESS($O41, COLUMN(I$1), 1, 1, $C41), 1), "н/д")
```
Builds a cell reference dynamically from a sheet name in column C.
Most flexible but harder to debug.

## Key insight
Method 2 (SUM across range) is the cleanest for uniform sheets. If you need to add
a new region, just insert the sheet between the first and last named sheets —
the formula automatically includes it.

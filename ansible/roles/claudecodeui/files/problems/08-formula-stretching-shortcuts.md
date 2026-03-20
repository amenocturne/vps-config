# Efficient formula stretching with keyboard

## Problem
Need to fill a formula across hundreds of columns (e.g., A to BA = 53 columns).
Dragging with mouse is slow and error-prone.

## Solution

### Method 1: Fill Right (fastest)
1. Select the cell with the formula
2. Place a delimiter value in the last target column (or use Ctrl+End to find it)
3. `Ctrl+Shift+Right` — selects from current cell to the delimiter
4. `Ctrl+R` — fills the formula rightward across selection

### Method 2: Copy + Paste Special
1. Copy the formula cell (`Ctrl+C`)
2. Select target range (`Ctrl+Shift+Right`)
3. Paste Special → Formulas only (avoids copying formatting)

### What NOT to do
- Don't drag the fill handle with mouse/touchpad
- Don't use Shift+Arrow to extend selection one cell at a time
- Don't use Ctrl+V (brings formatting along)

### Reference locking for stretching
Use F4 to cycle through lock modes:
- `$A$1` — fully locked (nothing moves)
- `A$1` — row locked (column moves when stretching right)
- `$A1` — column locked (row moves when stretching down)
- `A1` — unlocked (both move)

## Key insight
The delimiter trick (putting a value in the last column) gives Ctrl+Shift+Right
a stopping point. Without it, the selection jumps to the end of the sheet.
Alternatively, hide columns beyond your range with Ctrl+).

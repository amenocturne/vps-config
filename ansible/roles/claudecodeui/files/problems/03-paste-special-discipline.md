# Paste Special: avoiding style and link pollution

## Problem
Copying data from another workbook with Ctrl+V brings unwanted formatting, styles,
and external links. The destination file becomes bloated, slow, and shows
"Update Links?" prompts on every open.

## Solution
Three paste modes to use instead of Ctrl+V:

1. **Values only** (Ctrl+Shift+V → Values): strips formulas, formatting, links.
   Use when you just need the data.

2. **Formulas only**: keeps formulas but strips formatting.
   If formulas reference another workbook, break links after pasting:
   Data → Edit Links → Break Link.

3. **Format only**: copies only cell formatting (colors, borders, number formats).

Never move/copy entire sheets between workbooks — it carries all styles with it.

## Key insight
External links are the most insidious problem. They're invisible until someone opens
the file and gets "Update Links?" or sees #REF! errors. Always break links
immediately after pasting formulas from external sources.

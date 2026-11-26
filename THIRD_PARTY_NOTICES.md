# Third-party notices

## trader-skill

- Source: https://github.com/Jakeschincariol/trader-skill
- Licence: MIT (full text below)

The paper portfolio layer (`screener.py`, `sizing.py`, `risk_limits.py`, `rebalance.py`) borrows
its ideas from four skills in that repository: `trader-screener`, `trader-budget`, `trader-risk`
and `trader-rebalance`. Its code was **not copied**. We wrote new code in this project's style for
Indian markets (NSE equities, INR, whole shares, cutoff-safe local prices). The US-only parts were
left out: SEC/13F data, the NYSE calendar, US tax rules, USD and broker order formats. This project
places no orders.

```text
MIT License

Copyright (c) 2026 Jake Schincariol

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

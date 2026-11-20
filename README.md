# Powerball Generator

A polished desktop Powerball play-slip generator that pulls real draw history, tracks what each batch costs, and keeps the lines you generate distinct.

## Features

- **Live historical data** — fetches ~10 years of actual Powerball results from the NY Open Data API on launch
- **Live cost tracking** — shows the last generation, session total, and per-line cost. The standard U.S. price is prefilled at $2; change it for local rules or add-ons.
- **Unique-line coverage** — prevents duplicate combinations while a play slip is on screen, so a batch does not accidentally buy the same line twice.
- **Coverage Coach** — shows how many distinct jackpot combinations the current play slip covers and explains why duplicate lines do not expand that coverage.
- **Your own numbers** — add five white balls and a Powerball manually; they receive the same duplicate, budget, display, and export handling as generated lines.
- **6 generation modes:**
  - **Trend Signal** — gives recent draws up to 3× the weight of older history
  - **Pure Random** — every number equally likely, no weighting
  - **Pattern Guard** — avoids birthday-heavy selections and obvious sequences, which may reduce jackpot-sharing if a line wins
  - **Hot Numbers** — weighted toward the most frequently drawn numbers
  - **Cold Numbers** — weighted toward the least frequently drawn (overdue) numbers
  - **Balanced Mix** — 3 hot white balls + 2 cold whites + cold Powerball
- **Batch generation** — generate 1–20 picks at a time
- **Print or save as PDF** — open the current play slip in your browser’s print dialog
- **Save to .txt** — export all generated picks with price and total-cost records
- **Offline fallback** — if the API is unreachable, falls back to pure random with uniform weights

## Requirements

- **Python 3.8+**
- **macOS or Windows** with a Python installation that includes tkinter (source use)
- **Internet connection** for fetching historical draw data (optional — works offline in pure random mode)

No pip packages required to run the app directly. PyInstaller is only needed if you want to build a standalone `.app` bundle.

## Quick Start

```bash
python3 powerball_generator.py
```

That's it. The app opens centered, fetches data in the background, and you're ready to generate. A startup message explains that historical records require an internet connection. Select **Don’t show this again** to hide it on future launches. Pure Random mode is available offline.

## Building a Standalone App and ZIP

Install PyInstaller in a build environment and run the builder on the target operating system. It creates a macOS app or a Windows application folder and packages it as a ZIP. Test each platform separately.

```bash
python -m pip install "pyinstaller>=6.11,<7"
python build.py
```

**Output:**
```
dist/PowerballGenerator.app    ← double-click to run
dist/PowerballGenerator        ← Windows application folder when built on Windows
dist/PowerballGenerator-macOS.zip or PowerballGenerator-Windows.zip
```

**Install to Applications (optional):**
```bash
cp -r dist/PowerballGenerator.app /Applications/
```

> **Note:** The app is unsigned. On first launch, macOS will block it. Right-click → Open, or go to System Settings → Privacy & Security → Open Anyway.

## File Structure

```
powerball_generator.py    ← main app
build_powerball.sh        ← PyInstaller build script
README.md                 ← this file
```

## How the Modes Work

| Mode | White Balls | Powerball | Strategy |
|------|------------|-----------|----------|
| Trend Signal | Recent history weighted 3× → 1× | Same | Data-guided recency heuristic |
| Pure Random | Uniform 1–69 | Uniform 1–26 | No historical weighting |
| Pattern Guard | Avoids common player patterns | Uniform | May reduce prize-sharing, not draw odds |
| Hot Numbers | Frequency-weighted | Frequency-weighted | Historical-frequency view |
| Cold Numbers | Inverse frequency-weighted | Inverse frequency-weighted | Historical-frequency view |
| Balanced Mix | 3 hot + 2 cold | Cold-weighted | Blended historical view |

All weighted modes use +1 Laplace smoothing so every number has a nonzero chance of being picked. Trend Signal weights the most recent 120 results more heavily. These are selection heuristics, not predictions.

## Data Source

Powerball drawing results from the [NY Open Data Lottery API](https://data.ny.gov/Government-Finance/Lottery-Powerball-Winning-Numbers-Beginning-2010/d6yy-54nr). Data is fetched live on each launch with a 20-second timeout.

## Disclaimer

This is a play-slip generator for entertainment. History-based modes are useful ways to choose numbers, but they do not change the probability of the next draw. The two practical safeguards are avoiding duplicate lines and, with Pattern Guard, possibly avoiding a shared jackpot. Play responsibly.

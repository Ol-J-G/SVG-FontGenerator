# svg2ttf — SVG to TrueType Font Generator

Converts individual SVG glyph files into a valid TrueType (`.ttf`) font.

## Quick Start

```bash
sudo apt install python3.12-venv   # Debian/Ubuntu only, once
./makefont glyphs/ -o MyFont.ttf --family "MyFont"
```

The `makefont` script creates a Python virtual environment (`.venv`), installs [fonttools](https://github.com/fonttools/fonttools) v4.63+ if needed, and runs `svg2ttf.py` with your arguments.

## Prerequisites

- Python 3.8+
- `python3-venv` (required once, install e.g. in Linux via `sudo apt install python3.12-venv`)

## Usage

```
./makefont <input_dir> -o <output.ttf> [--family <name>] [--style <name>] [--upem <units>] [--bold <amount>] [--narrow <amount>] [--version <ver>] [--author <name>] [--manufacturer <name>] [--copyright <text>] [--license <text>]
```

### Arguments

| Argument | Default | Description |
|---|---|---|
| `input_dir` | — | Directory containing `0x*.svg` files (searches recursively) |
| `-o, --output` | `output.ttf` | Output font file |
| `--family` | `MyFont` | Font family name |
| `--style` | `Regular` | Font style name (auto-sets to `Bold` if `--bold > 0`) |
| `--upem` | `1000` | Units per em |
| `--bold` | `0` | Outline expansion in font units (0 = no bold) |
| `--narrow` | `0` | Horizontal scaling in font units (0 = no narrow) |
| `--version` | `1.0` | Font version string (embedded as "Version X.Y") |
| `--author` | — | Author/manufacturer name (nameID 8) |
| `--copyright` | — | Copyright notice (nameID 0) |
| `--license` | — | License description (nameID 13) |

## Input Format

Place SVG files in the input directory named by Unicode codepoint:

```
glyphs/latin/
├── 0x0041.svg   → U+0041 = 'A'
├── 0x0042.svg   → U+0042 = 'B'
├── 0x0032.svg   → U+0032 = '2'
└── 0x002E.svg   → U+002E = '.'
```

Each SVG must:
- Have a `viewBox` attribute (e.g. `viewBox="0 0 600 800"`)
- Contain `<path>` elements with `d` attributes
- Use any fill rule; paths are converted to quadratic TrueType outlines

How I create the glyphs:
- Create a SVG document of your choice (e.g. 144x208 pixel) with Inkscape (available on many platforms)
- Draw the glyph
- Save SVG file to <input_folder> (organized in sub folders)

### Example

```
./makefont glyphs/ -o MyFont.ttf --family "MyFont"
```

## Output

The font includes three built-in glyphs:
- **`.notdef`** — full-em rectangle (glyph 0)
- **`.null`** — empty glyph (glyph 1, not mapped)
- **`space`** — empty glyph at advance=500 (glyph 2, mapped to U+0020)

A space character (U+0020) in the cmap and a complete name table (nameIDs 1–6) are required for Windows 11 compatibility.

## Bold Variants

Create a bold variant by expanding outlines outward:

```bash
./makefont glyphs/latin/ -o MyFont-Bold.ttf --bold 50
```

This expands each glyph outline by the specified amount (in font units). The script automatically:
- Sets the style name to `Bold` (unless `--style` is explicitly provided)
- Sets `OS/2.usWeightClass = 700`
- Sets the bold bit in `head.macStyle` and `OS/2.fsSelection`

The offset algorithm flattens curves to line segments, computes outward normals, and applies miter joins at corners.

## Narrow Variants

Create a condensed/narrow variant by scaling glyphs horizontally:

```bash
./makefont glyphs/latin/ -o MyFont-Condensed.ttf --narrow 250
```

The `--narrow` value is in font units (same as `--bold`). The horizontal scale factor is:

```
scale_x = 1.0 - (narrow / 1000.0)
```

| narrow | scale_x | Effect |
|--------|---------|--------|
| 50 | 0.95 | 5% narrower (SemiCondensed) |
| 100 | 0.90 | 10% narrower (Condensed) |
| 250 | 0.75 | 25% narrower (ExtraCondensed) |

Unlike `--bold`, narrow scaling also reduces the advance width proportionally. Can be combined with `--bold`:

```bash
./makefont glyphs/latin/ -o MyFont-CondensedBold.ttf --bold 50 --narrow 250
```

The script automatically sets the style name (`Condensed`, `Condensed Bold`) and `OS/2.usWidthClass` based on the narrow amount.

## Metadata

Optional parameters embed font metadata into the name table:

```bash
./makefont glyphs/ -o MyFont.ttf --family "MyFont" \
  --version "2.0" \
  --author "Jane Doe" \
  --manufacturer "Acme Corp" \
  --copyright "2026 Jane Doe" \
  --license "Licensed under the Apache License, Version 2.0"
```

| Parameter | Name ID | Example |
|---|---|---|
| `--version` | 5 (version) | `"2.0"` → "Version 2.0" |
| `--author` | 9 (designer) | `"Jane Doe"` |
| `--manufacturer` | 8 (manufacturer) | `"Acme Corp"` |
| `--copyright` | 0 (copyright) | `"2026 Jane Doe"` |
| `--license` | 13 (licenseDescription) | `"Licensed under the Apache License, Version 2.0"` |

When omitted, no extra metadata is added (version defaults to "Version 1.0").

## Technical Notes

- Cubic SVG bezier curves are converted to quadratic TrueType outlines using `Cu2QuPen`
- Glyphs are auto‑shifted so their lowest point sits on the baseline (y=0)
- Advance width is derived from the SVG `viewBox` width scaled to the UPM

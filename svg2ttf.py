#!/usr/bin/env python3
import argparse
import glob
import os
import re
import xml.etree.ElementTree as ET

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.svgLib.path import parse_path
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates


def scale_glyph(glyph, scale_x):
    """Scale a glyph's X coordinates about its horizontal center.

    This makes all vertical strokes wider (bolder) while preserving
    the original curve structure and point count.
    """
    if scale_x == 1.0 or glyph.numberOfContours <= 0:
        return glyph

    coords = glyph.coordinates
    if not coords:
        return glyph

    xs = [x for x, y in coords]
    cx = (min(xs) + max(xs)) / 2.0
    if min(xs) == max(xs):
        return glyph

    new_coords = GlyphCoordinates([(cx + (x - cx) * scale_x, y) for x, y in coords])
    glyph.coordinates = new_coords
    return glyph


def svg_to_glyph(svg_path, upem, y_offset=0):
    """Convert SVG to glyph, returning (glyph, advance).

    If y_offset is 0, computes per-glyph y_offset (legacy behavior).
    If y_offset is provided, uses it as a fixed baseline offset.
    """
    tree = ET.parse(svg_path)
    root = tree.getroot()

    vb = root.get("viewBox", "0 0 0 0").split()
    _, _, vb_w, vb_h = map(float, vb)

    path_elements = root.findall(".//{http://www.w3.org/2000/svg}path")
    if not path_elements:
        path_elements = root.findall(".//path")

    scale = upem / vb_h
    base_transform = (scale, 0, 0, -scale, 0, upem)

    # Compute y_offset if not provided
    if y_offset == 0:
        temp_ttpen = TTGlyphPen(None)
        temp_qpen = Cu2QuPen(temp_ttpen, max_err=1.0)
        temp_tpen = TransformPen(temp_qpen, base_transform)
        for path_el in path_elements:
            d = path_el.get("d", "")
            if d:
                parse_path(d, temp_tpen)
        temp_glyph = temp_ttpen.glyph()
        if temp_glyph.numberOfContours > 0 and len(temp_glyph.coordinates) > 0:
            y_offset = -min(y for _, y in temp_glyph.coordinates)
        else:
            y_offset = 0

    # Render with y_offset applied
    transform = (scale, 0, 0, -scale, 0, upem + y_offset)

    tt_pen = TTGlyphPen(None)
    qpen = Cu2QuPen(tt_pen, max_err=1.0)
    tpen = TransformPen(qpen, transform)
    for path_el in path_elements:
        d = path_el.get("d", "")
        if d:
            parse_path(d, tpen)

    glyph = tt_pen.glyph()
    advance = round(vb_w * scale)
    return glyph, advance


def build_font(glyph_list, upem, family="MyFont", style="Regular", bold_amount=0, narrow_amount=0):
    glyph_list = sorted(glyph_list, key=lambda x: x[0])

    glyph_order = [".notdef", ".null", "space"]
    cmap = {}
    glyphs = {}
    metrics = {}

    space_advance = 500

    null_pen = TTGlyphPen(None)
    glyphs[".null"] = null_pen.glyph()
    metrics[".null"] = (space_advance, 0)

    space_pen = TTGlyphPen(None)
    glyphs["space"] = space_pen.glyph()
    metrics["space"] = (space_advance, 0)
    cmap[0x0020] = "space"

    for codepoint, glyph_name, glyph, advance in glyph_list:
        glyph_order.append(glyph_name)
        cmap[codepoint] = glyph_name
        glyphs[glyph_name] = glyph
        metrics[glyph_name] = (advance, 0)

    all_advances = {space_advance} | {a for _, _, _, a in glyph_list}
    notdef_advance = max(all_advances) + 1

    notdef_pen = TTGlyphPen(None)
    notdef_pen.moveTo((0, 0))
    notdef_pen.lineTo((notdef_advance, 0))
    notdef_pen.lineTo((notdef_advance, upem))
    notdef_pen.lineTo((0, upem))
    notdef_pen.closePath()
    glyphs[".notdef"] = notdef_pen.glyph()
    metrics[".notdef"] = (notdef_advance, 0)

    fb = FontBuilder(upem, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    fb.calcGlyphBounds()

    glyf_table = fb.font["glyf"]
    for gn in glyph_order:
        w = metrics[gn][0]
        metrics[gn] = (w, glyf_table[gn].xMin)

    fb.setupHorizontalMetrics(metrics)
    descent = int(upem * -0.2)
    fb.setupHorizontalHeader(ascent=upem, descent=descent)
    fb.setupNameTable({
        "familyName": family,
        "styleName": style,
        "uniqueFontIdentifier": f"fontBuilder: {family}.{style}",
        "fullName": f"{family} {style}",
        "psName": f"{family}-{style}",
        "version": "Version 1.0",
    })
    fb.setupOS2(
        sTypoAscender=upem,
        sTypoDescender=descent,
        usWinAscent=upem,
        usWinDescent=int(upem * 0.2),
        fsType=0,
        fsSelection=0x0040,
        sxHeight=int(upem * 0.5),
        sCapHeight=int(upem * 0.7),
        ulCodePageRange1=0x00000001,
        usMaxContext=1,
        yStrikeoutSize=50,
        yStrikeoutPosition=int(upem * 0.22),
        ySubscriptXSize=650,
        ySubscriptYSize=600,
        ySubscriptXOffset=0,
        ySubscriptYOffset=75,
        ySuperscriptXSize=650,
        ySuperscriptYSize=600,
        ySuperscriptXOffset=0,
        ySuperscriptYOffset=350,
    )
    fb.setupPost(keepGlyphNames=False)

    font = fb.font
    font["head"].macStyle = 0
    font["OS/2"].version = 4
    font["OS/2"].usLowerOpticalPointSize = 0
    font["OS/2"].usUpperOpticalPointSize = 0

    if bold_amount > 0:
        font["OS/2"].usWeightClass = 700
        font["head"].macStyle |= (1 << 0)
        font["OS/2"].fsSelection = 0x0020

    if narrow_amount > 0:
        if narrow_amount < 50:
            font["OS/2"].usWidthClass = 4  # SemiCondensed
        elif narrow_amount < 100:
            font["OS/2"].usWidthClass = 3  # Condensed
        else:
            font["OS/2"].usWidthClass = 2  # ExtraCondensed

    return font


def main():
    parser = argparse.ArgumentParser(
        description="Convert SVG glyphs (0x*.svg) to a TrueType font"
    )
    parser.add_argument("input_dir", help="Directory containing 0x*.svg files")
    parser.add_argument("-o", "--output", default="output.ttf", help="Output TTF path")
    parser.add_argument("--family", default="MyFont", help="Font family name")
    parser.add_argument("--style", default=None, help="Font style (default: Regular, or Bold if --bold > 0)")
    parser.add_argument("--upem", type=int, default=1000, help="Units per em")
    parser.add_argument("--bold", type=float, default=0,
                        help="Bold scale factor in font units: scale_x = 1 + bold/1000 (0=no bold, 50=5%% wider, 100=10%% wider)")
    parser.add_argument("--narrow", type=float, default=0,
                        help="Narrow scale factor: scale_x = 1 - narrow/1000 (0=normal, 100=10%% narrower)")
    args = parser.parse_args()

    style = args.style
    if style is None:
        if args.bold > 0 and args.narrow > 0:
            style = "Condensed Bold"
        elif args.bold > 0:
            style = "Bold"
        elif args.narrow > 0:
            style = "Condensed"
        else:
            style = "Regular"

    files = sorted(glob.glob(os.path.join(args.input_dir, "0x*.svg")))
    if not files:
        print(f"No 0x*.svg files found in {args.input_dir}")
        return

    # First pass: compute global baseline offset from all glyphs
    y_mins = []
    for fpath in files:
        basename = os.path.basename(fpath)
        m = re.match(r"0x([0-9a-fA-F]+)\.svg", basename)
        if not m:
            continue
        tree = ET.parse(fpath)
        root = tree.getroot()
        vb = root.get("viewBox", "0 0 0 0").split()
        _, _, vb_w, vb_h = map(float, vb)
        scale = args.upem / vb_h

        path_elements = root.findall(".//{http://www.w3.org/2000/svg}path")
        if not path_elements:
            path_elements = root.findall(".//path")

        temp_ttpen = TTGlyphPen(None)
        temp_qpen = Cu2QuPen(temp_ttpen, max_err=1.0)
        temp_tpen = TransformPen(temp_qpen, (scale, 0, 0, -scale, 0, args.upem))
        for path_el in path_elements:
            d = path_el.get("d", "")
            if d:
                parse_path(d, temp_tpen)
        temp_glyph = temp_ttpen.glyph()
        if temp_glyph.numberOfContours > 0 and len(temp_glyph.coordinates) > 0:
            y_mins.append(-min(y for _, y in temp_glyph.coordinates))

    # Use median yMin as global baseline offset (robust to descender outliers)
    if y_mins:
        y_mins.sort()
        global_y_offset = y_mins[len(y_mins) // 2]
    else:
        global_y_offset = 0

    # Second pass: render all glyphs with global baseline offset
    glyph_list = []
    for fpath in files:
        basename = os.path.basename(fpath)
        m = re.match(r"0x([0-9a-fA-F]+)\.svg", basename)
        if not m:
            continue
        codepoint = int(m.group(1), 16)
        glyph_name = f"uni{codepoint:04X}"
        glyph, advance = svg_to_glyph(fpath, args.upem, y_offset=global_y_offset)

        # Apply bold scaling if requested
        if args.bold > 0:
            scale_x = 1.0 + (args.bold / 1000.0)
            glyph = scale_glyph(glyph, scale_x)

        # Apply narrow scaling if requested
        if args.narrow > 0:
            scale_x = 1.0 - (args.narrow / 1000.0)
            glyph = scale_glyph(glyph, scale_x)
            advance = round(advance * scale_x)

        glyph_list.append((codepoint, glyph_name, glyph, advance))

    font = build_font(glyph_list, args.upem, args.family, style, bold_amount=args.bold, narrow_amount=args.narrow)
    font.save(args.output)
    print(f"Saved {args.output} with {len(glyph_list)} glyphs")


if __name__ == "__main__":
    main()

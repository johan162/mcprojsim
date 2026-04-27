#!/usr/bin/env bash
# mkragged.dh — Create a torn-edge version of a PNG image.
#
# Usage:
#   mkragged.dh [--raggedness N] [--mode MODE] [--paper-color COLOR] -o OUTPUT.png INPUT.png
#
# Modes:
#   transparent         Torn edges on a transparent background.
#   transparent-shadow  Torn edges on a transparent background with a soft shadow
#                      behind the paper edge, useful when compositing onto another design.
#   paper               Torn edges composited onto a paper-colored background.
#
# Typical examples:
#   mkragged.dh -o out.png in.png
#   mkragged.dh --mode transparent-shadow -o out.png in.png
#   mkragged.dh --mode paper --paper-color '#f8f1e3' -o out.png in.png
#
# The output keeps the original image content but applies an irregular,
# feathered alpha mask so the edges look torn from a page.

set -euo pipefail

show_help() {
    cat << EOF
Usage:
    $0 [--raggedness N] [--mode MODE] [--paper-color COLOR] -o OUTPUT.png INPUT.png

Create a version of a PNG image with ragged, torn-looking edges.

Options:
    -o, --output FILE     Output PNG path (required)
    -r, --raggedness N    Raggedness amount in pixels (default: 28)
    -m, --mode MODE       Output mode: transparent, transparent-shadow, or paper
                          (default: transparent)
    --paper-color COLOR   Paper background color for paper mode (default: #f5efe2)
    -h, --help            Show this help message and exit

Arguments:
    INPUT.png             Source PNG image

Notes:
    - Higher raggedness creates deeper tears and a rougher edge.
        - Transparent mode keeps PNG transparency around the torn edges.
        - Transparent-shadow mode keeps transparency and adds a soft shadow
            behind the torn image for easier compositing onto other artwork.
        - Paper mode composites the torn image onto a paper-colored background.
    - Requires ImageMagick (magick or convert + identify).

Examples:
    $0 -o out.png in.png
    $0 --raggedness 42 -o out.png in.png
    $0 --mode transparent-shadow -o out.png in.png
    $0 --mode paper --paper-color '#f8f1e3' -o out.png in.png
EOF
}

OUTPUT=""
INPUT=""
RAGGEDNESS=10
MODE="transparent"
PAPER_COLOR="#f5efe2"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -o|--output)
            OUTPUT="$2"
            shift 2
            ;;
        --output=*)
            OUTPUT="${1#--output=}"
            shift
            ;;
        -r|--raggedness)
            RAGGEDNESS="$2"
            shift 2
            ;;
        --raggedness=*)
            RAGGEDNESS="${1#--raggedness=}"
            shift
            ;;
        -m|--mode)
            MODE="$2"
            shift 2
            ;;
        --mode=*)
            MODE="${1#--mode=}"
            shift
            ;;
        --paper-color)
            PAPER_COLOR="$2"
            shift 2
            ;;
        --paper-color=*)
            PAPER_COLOR="${1#--paper-color=}"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        -*)
            echo "Error: unknown option: $1" >&2
            exit 1
            ;;
        *)
            if [[ -z "$INPUT" ]]; then
                INPUT="$1"
            else
                echo "Error: unexpected extra argument: $1" >&2
                exit 1
            fi
            shift
            ;;
    esac
done

if [[ -z "$INPUT" || -z "$OUTPUT" ]]; then
    echo "Error: INPUT.png and --output are required." >&2
    echo "Try '$0 --help' for usage." >&2
    exit 1
fi

if [[ ! -f "$INPUT" ]]; then
    echo "Error: input file not found: $INPUT" >&2
    exit 1
fi

if [[ "${INPUT##*.}" != "png" && "${INPUT##*.}" != "PNG" ]]; then
    echo "Error: input must be a PNG image." >&2
    exit 1
fi

if ! [[ "$RAGGEDNESS" =~ ^[0-9]+$ ]] || [[ "$RAGGEDNESS" -lt 4 ]]; then
    echo "Error: --raggedness must be an integer >= 4." >&2
    exit 1
fi

if [[ "$MODE" != "transparent" && "$MODE" != "transparent-shadow" && "$MODE" != "paper" ]]; then
    echo "Error: --mode must be 'transparent', 'transparent-shadow', or 'paper'." >&2
    exit 1
fi

if command -v magick >/dev/null 2>&1; then
    IM=(magick)
    IDENTIFY=(magick identify)
elif command -v convert >/dev/null 2>&1 && command -v identify >/dev/null 2>&1; then
    IM=(convert)
    IDENTIFY=(identify)
else
    echo "Error: ImageMagick not found (need 'magick' or 'convert' + 'identify')." >&2
    exit 1
fi

mkdir -p "$(dirname "$OUTPUT")"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

MASK="$WORKDIR/mask.png"
MASK_SOFT="$WORKDIR/mask-soft.png"
NIBBLES="$WORKDIR/nibbles.mvg"
POLYGON_FILE="$WORKDIR/polygon.txt"
TORN="$WORKDIR/torn.png"
PAPER_BG="$WORKDIR/paper-bg.png"
PAPER_NOISE="$WORKDIR/paper-noise.png"
SHADOW_MASK="$WORKDIR/shadow-mask.png"

DIMENSIONS=$("${IDENTIFY[@]}" -format "%w %h" "$INPUT")
read -r WIDTH HEIGHT <<< "$DIMENSIONS"

MARGIN=$(( RAGGEDNESS / 3 ))
if [[ "$MARGIN" -lt 6 ]]; then
    MARGIN=6
fi

STEP=$(( RAGGEDNESS / 2 ))
if [[ "$STEP" -lt 14 ]]; then
    STEP=14
fi

BLUR_RADIUS=$(awk -v r="$RAGGEDNESS" 'BEGIN { printf "%.1f", (r < 20 ? 1.2 : r / 16.0) }')

awk \
    -v width="$WIDTH" \
    -v height="$HEIGHT" \
    -v ragged="$RAGGEDNESS" \
    -v margin="$MARGIN" \
    -v step="$STEP" \
    '
    function clamp(v, lo, hi) {
        return v < lo ? lo : (v > hi ? hi : v)
    }
    function smooth(prev, target, amount) {
        return prev * (1.0 - amount) + target * amount
    }
    function edge_offset(prev, base, rough, bias,   t, val) {
        t = base + rand() * rough
        if (rand() < 0.16) {
            t += rand() * rough * bias
        }
        val = smooth(prev, t, 0.42)
        return clamp(val, base * 0.7, base + rough * 1.55)
    }
    BEGIN {
        srand()

        n = 0
        prev = margin + ragged * 0.55
        for (x = 0; x <= width; x += step) {
            prev = edge_offset(prev, margin, ragged, 0.9)
            px[++n] = x
            py[n] = prev
        }
        if (px[n] != width) {
            prev = edge_offset(prev, margin, ragged, 0.9)
            px[++n] = width
            py[n] = prev
        }

        prev = margin + ragged * 0.48
        for (y = step; y <= height; y += step) {
            prev = edge_offset(prev, margin, ragged, 0.85)
            px[++n] = width - prev
            py[n] = y
        }
        if (py[n] != height) {
            prev = edge_offset(prev, margin, ragged, 0.85)
            px[++n] = width - prev
            py[n] = height
        }

        prev = margin + ragged * 0.55
        for (x = width - step; x >= 0; x -= step) {
            prev = edge_offset(prev, margin, ragged, 1.0)
            px[++n] = x
            py[n] = height - prev
        }
        if (px[n] != 0) {
            prev = edge_offset(prev, margin, ragged, 1.0)
            px[++n] = 0
            py[n] = height - prev
        }

        prev = margin + ragged * 0.5
        for (y = height - step; y >= 0; y -= step) {
            prev = edge_offset(prev, margin, ragged, 0.85)
            px[++n] = prev
            py[n] = y
        }

        out = "polygon"
        for (i = 1; i <= n; i++) {
            out = out sprintf(" %d,%d", int(px[i]), int(py[i]))
        }
        print out
    }
    ' > "$POLYGON_FILE"

POLYGON=$(cat "$POLYGON_FILE")

"${IM[@]}" -size "${WIDTH}x${HEIGHT}" xc:black \
    -fill white \
    -draw "$POLYGON" \
    "$MASK"

awk \
    -v width="$WIDTH" \
    -v height="$HEIGHT" \
    -v ragged="$RAGGEDNESS" \
    '
    BEGIN {
        srand()
        print "viewbox 0 0 " width " " height
        print "fill black"
        count = int(width / 220) + int(height / 260) + 4
        for (i = 0; i < count; i++) {
            side = int(rand() * 4)
            radius = ragged * (0.35 + rand() * 0.55)

            if (side == 0) {
                cx = rand() * width
                cy = rand() * (ragged * 0.7)
            } else if (side == 1) {
                cx = width - rand() * (ragged * 0.7)
                cy = rand() * height
            } else if (side == 2) {
                cx = rand() * width
                cy = height - rand() * (ragged * 0.7)
            } else {
                cx = rand() * (ragged * 0.7)
                cy = rand() * height
            }

            print "circle " int(cx) "," int(cy) " " int(cx + radius) "," int(cy)
        }
    }
    ' > "$NIBBLES"

"${IM[@]}" "$MASK" \
    -draw @"$NIBBLES" \
    -blur "0x${BLUR_RADIUS}" \
    -level 25%,100% \
    "$MASK_SOFT"

"${IM[@]}" "$INPUT" \
    "$MASK_SOFT" -alpha off -compose CopyOpacity -composite \
    -background none \
    "$TORN"

"${IM[@]}" "$MASK_SOFT" \
    -blur "0x$(( RAGGEDNESS / 5 < 2 ? 2 : RAGGEDNESS / 5 ))" \
    -level 0%,55% \
    "$SHADOW_MASK"

if [[ "$MODE" == "transparent" ]]; then
    mv "$TORN" "$OUTPUT"
    exit 0
fi

if [[ "$MODE" == "transparent-shadow" ]]; then
    "${IM[@]}" -size "${WIDTH}x${HEIGHT}" xc:none \
        \( "$SHADOW_MASK" -background none -alpha copy -channel A -separate +channel \
           -fill 'rgba(50,35,20,0.32)' -colorize 100 -geometry +0+0 \) \
        -compose over -composite \
        "$TORN" -compose over -composite \
        "$OUTPUT"
    exit 0
fi

"${IM[@]}" -size "${WIDTH}x${HEIGHT}" "xc:${PAPER_COLOR}" "$PAPER_BG"

"${IM[@]}" -size "${WIDTH}x${HEIGHT}" xc:none \
    +noise Random \
    -colorspace gray \
    -evaluate multiply 0.12 \
    "$PAPER_NOISE"

"${IM[@]}" "$PAPER_BG" "$PAPER_NOISE" -compose multiply -composite "$PAPER_BG"

"${IM[@]}" "$PAPER_BG" \
    \( "$SHADOW_MASK" -background none -alpha copy -channel A -separate +channel \
       -fill 'rgba(70,45,20,0.22)' -colorize 100 \) \
    -compose over -composite \
    "$TORN" -compose over -composite \
    "$OUTPUT"

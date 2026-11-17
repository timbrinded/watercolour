#!/usr/bin/env bash
# Paint the value bands of a style target in order, each pass measured from the dry look the last one left.
# Usage: paint_bands.sh <painting dir> <target.png> <W,H> <paints> <first band index> <threshold>[:extra args] ...
set -euo pipefail
painting=$1 target=$2 sheet=$3 paints=$4 first=$5
shift 5
here=$(cd "$(dirname "$0")" && pwd)
python=${PYTHON:-$(dirname "$(readlink -f "$(command -v watercolor)")")/python}
look=$(watercolor look "$painting" | "$python" -c 'import json,sys; print(json.load(sys.stdin)["look"])')
index=$first
for band in "$@"; do
    threshold=${band%%:*}
    extra=""
    [[ $band == *:* ]] && extra=${band#*:}
    pass="${painting%/}.band${index}.json"
    # shellcheck disable=SC2086
    "$python" -I "$here/tonal_shapes.py" "$target" "$pass" --sheet "$sheet" --paints "$paints" \
        --threshold "$threshold" --look "$look" --preview "${painting%/}.band${index}.preview.png" $extra
    look=$(watercolor paint "$painting" "$pass" | "$python" -c 'import json,sys; print(json.load(sys.stdin)["look"])')
    echo "band $index ($threshold) done: $look"
    index=$((index + 1))
done

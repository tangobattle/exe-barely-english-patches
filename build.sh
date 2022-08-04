#!/bin/bash
set -euo pipefail

FLIPS=${FLIPS:-'flips'}

set -x

make_patch() {
    ./make_rom.py "${1}.toml" "${2}" "${3}" "${1}-en.gba"
    "$FLIPS" --create "${2}" "${1}-en.gba" "${1}-en.bps"
}

make_patch exe4bm10 bn4bm.gba exe4bm10.gba
make_patch exe4rs11 bn4rs.gba exe4rs11.gba
make_patch exe5b bn5p.gba exe5b.gba
make_patch exe5c bn5c.gba exe5c.gba

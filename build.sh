#!/bin/bash
set -euo pipefail

FLIPS=${FLIPS:-'flips'}

set -x

make_patch() {
    ./make_rom.py "${1}.toml" "${2}" "${3}" "${1}-en.gba"
    "$FLIPS" --create "${2}" "${1}-en.gba" "${4}"
}

make_patch exe4bm10 bn4bm.gba exe4bm10.gba patches/exe4_barely_english/v0.0.0/ROCK_EXE4_BMB4BJ_00.bps
make_patch exe4rs11 bn4rs.gba exe4rs11.gba patches/exe4_barely_english/v0.0.0/ROCK_EXE4_RSB4WJ_01.bps
make_patch exe5b bn5p.gba exe5b.gba patches/exe5_barely_english/v0.0.0/ROCKEXE5_TOBBRBJ_00.bps
make_patch exe5c bn5c.gba exe5c.gba patches/exe5_barely_english/v0.0.0/ROCKEXE5_TOCBRKJ_00.bps

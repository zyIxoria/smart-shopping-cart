#!/usr/bin/env bash
# Chạy unit test của cartcore bằng g++ (không cần PlatformIO). Dùng bản shim của Unity.
# Với PlatformIO thật hãy dùng:  pio test -e native
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .build
g++ -std=c++11 -Wall -Wextra -Wno-unused-function -fsanitize=address,undefined -g \
    -Ilib/cartcore -Itools/unity_shim \
    lib/cartcore/cartcore.cpp lib/cartcore/cartsec.cpp test/test_cartcore/test_main.cpp -o .build/native_tests
.build/native_tests

#!/bin/sh
set -eu

TEST_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
JAVA_DIR="$TEST_DIR/../app/src/main/java/best/lmm/snapveil"
TEST_BUILD_DIR=$(mktemp -d "${TMPDIR:-/tmp}/snapveil-java-test.XXXXXX")
trap 'rm -rf "$TEST_BUILD_DIR"' EXIT HUP INT TERM

javac --release 8 -encoding UTF-8 -Xlint:all -Werror -d "$TEST_BUILD_DIR" \
  "$JAVA_DIR/ScreenshotGate.java" \
  "$JAVA_DIR/ReflectionAccess.java" \
  "$TEST_DIR/ScreenshotGateTest.java"
java -cp "$TEST_BUILD_DIR" best.lmm.snapveil.ScreenshotGateTest

#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPILER="$SCRIPT_DIR/../src/compiler.py"
VALID_DIR="$SCRIPT_DIR/valid"
INVALID_DIR="$SCRIPT_DIR/invalid"

PASS=0
FAIL=0
TOTAL=0
FAILED_TESTS=""

green() { printf "\033[32m%s\033[0m" "$1"; }
red()   { printf "\033[31m%s\033[0m" "$1"; }
bold()  { printf "\033[1m%s\033[0m" "$1"; }

echo ""
bold "═══ VALID TESTS (happy path) ═══"
echo ""

for txt in "$VALID_DIR"/*.txt; do
    name="$(basename "$txt" .txt)"
    expected="$VALID_DIR/${name}.expected"
    TOTAL=$((TOTAL + 1))

    if [ ! -f "$expected" ]; then
        red "  SKIP"
        echo " $name — missing .expected file"
        FAIL=$((FAIL + 1))
        FAILED_TESTS="$FAILED_TESTS  valid/$name (missing .expected)\n"
        continue
    fi

    actual=$(python3 "$COMPILER" --ast "$txt" 2>/dev/null)
    exit_code=$?

    if [ "$exit_code" -ne 0 ]; then
        red "  FAIL"
        echo " $name — compiler exited with code $exit_code"
        FAIL=$((FAIL + 1))
        FAILED_TESTS="$FAILED_TESTS  valid/$name (exit $exit_code)\n"
    elif [ "$actual" = "$(cat "$expected")" ]; then
        green "  PASS"
        echo " $name"
        PASS=$((PASS + 1))
    else
        red "  FAIL"
        echo " $name"
        FAIL=$((FAIL + 1))
        FAILED_TESTS="$FAILED_TESTS  valid/$name\n"
        echo "    Expected:"
        head -5 "$expected" | sed 's/^/      /'
        echo "    Got:"
        echo "$actual" | head -5 | sed 's/^/      /'
    fi
done

echo ""
bold "═══ INVALID TESTS (error scenarios) ═══"
echo ""

for txt in "$INVALID_DIR"/*.txt; do
    name="$(basename "$txt" .txt)"
    err_file="$INVALID_DIR/${name}.err"
    TOTAL=$((TOTAL + 1))

    if [ ! -f "$err_file" ]; then
        red "  SKIP"
        echo " $name — missing .err file"
        FAIL=$((FAIL + 1))
        FAILED_TESTS="$FAILED_TESTS  invalid/$name (missing .err)\n"
        continue
    fi

    # Capture stderr and stdout separately; don't mask exit code
    actual_stdout=$(python3 "$COMPILER" --ast "$txt" 2>/tmp/duck_test_stderr)
    actual_exit=$?
    actual_stderr=$(cat /tmp/duck_test_stderr)

    expected_stderr="$(cat "$err_file")"

    if [ "$actual_exit" -ne 0 ] && [ "$actual_stderr" = "$expected_stderr" ] && [ -z "$actual_stdout" ]; then
        green "  PASS"
        echo " $name"
        PASS=$((PASS + 1))
    else
        red "  FAIL"
        echo " $name"
        FAIL=$((FAIL + 1))
        FAILED_TESTS="$FAILED_TESTS  invalid/$name\n"
        if [ "$actual_exit" -eq 0 ]; then
            echo "    Expected non-zero exit, got 0"
        fi
        if [ -n "$actual_stdout" ]; then
            echo "    Expected no stdout, got: $actual_stdout"
        fi
        if [ "$actual_stderr" != "$expected_stderr" ]; then
            echo "    Expected stderr: $expected_stderr"
            echo "    Got stderr:      $actual_stderr"
        fi
    fi
done

rm -f /tmp/duck_test_stderr

echo ""
echo "─────────────────────────────────────"
bold "Results: "
green "$PASS passed"
echo -n ", "
if [ "$FAIL" -gt 0 ]; then
    red "$FAIL failed"
else
    echo -n "$FAIL failed"
fi
echo " out of $TOTAL total"

if [ "$FAIL" -gt 0 ]; then
    echo ""
    red "Failed tests:"
    echo ""
    printf "$FAILED_TESTS"
    exit 1
else
    echo ""
    green "All tests passed! 🦆"
    echo ""
    exit 0
fi

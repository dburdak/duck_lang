#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPILER="$SCRIPT_DIR/../compiler.py"
REPO_DIR="$SCRIPT_DIR/.."
PYTHON="${PYTHON:-python3}"
CLANG="${CLANG:-clang}"
if [ -x "$REPO_DIR/.venv/bin/python" ]; then
    PYTHON="$REPO_DIR/.venv/bin/python"
fi

TMP_DIR=$(mktemp -d)
TMP_OUT="$TMP_DIR/out"
TMP_ERR="$TMP_DIR/err"
trap 'rm -rf "$TMP_DIR"' EXIT

PASSED=0
FAILED=0
FAILED_LIST=()

echo "═══ CODE CHECKS ═══"
# Check forbidden methods/modules in all src/*.py files
FORBIDDEN_MATCHES=$(grep -nE "import re|\.split\(|\.decode\(|\.encode\(" "$REPO_DIR"/src/*.py | grep -v '\.decode("ascii")')
if [ -n "$FORBIDDEN_MATCHES" ]; then
    echo "  FAIL: Forbidden calls found in src/*.py:"
    echo "$FORBIDDEN_MATCHES"
    FAILED=$((FAILED + 1))
    FAILED_LIST+=("forbidden_code_check")
else
    echo "  PASS: No forbidden calls in src/*.py"
fi

# Check no --tokens in src/*.py or README.md
TOKENS_SRC=$(grep -n "\--tokens" "$REPO_DIR"/src/*.py)
TOKENS_README=$(grep -n "\--tokens" "$REPO_DIR/README.md")
if [ -n "$TOKENS_SRC" ] || [ -n "$TOKENS_README" ]; then
    echo "  FAIL: Found --tokens references:"
    [ -n "$TOKENS_SRC" ] && echo "    src/*.py: $TOKENS_SRC"
    [ -n "$TOKENS_README" ] && echo "    README.md: $TOKENS_README"
    FAILED=$((FAILED + 1))
    FAILED_LIST+=("tokens_flag_check")
else
    echo "  PASS: No --tokens flag references"
fi

echo ""
echo "═══ VALID TESTS (happy path) ═══"
for test_file in "$SCRIPT_DIR"/valid/*.txt; do
    [ -f "$test_file" ] || continue
    name=$(basename "$test_file" .txt)
    expected_file="$SCRIPT_DIR/valid/$name.expected"

    "$PYTHON" "$COMPILER" --ast "$test_file" > "$TMP_OUT" 2> "$TMP_ERR"
    exit_code=$?

    if [ $exit_code -ne 0 ]; then
        echo "  FAIL $name (exit code $exit_code, expected 0)"
        echo "Stderr:"
        cat "$TMP_ERR"
        FAILED=$((FAILED + 1))
        FAILED_LIST+=("valid/$name")
    elif ! diff -u "$expected_file" "$TMP_OUT" > "$TMP_ERR"; then
        echo "  FAIL $name (AST output mismatch)"
        cat "$TMP_ERR"
        FAILED=$((FAILED + 1))
        FAILED_LIST+=("valid/$name")
    else
        echo "  PASS $name"
        PASSED=$((PASSED + 1))
    fi
done

echo ""
echo "═══ INVALID TESTS (error scenarios) ═══"
for test_file in "$SCRIPT_DIR"/invalid/*.txt; do
    [ -f "$test_file" ] || continue
    name=$(basename "$test_file" .txt)
    err_file="$SCRIPT_DIR/invalid/$name.err"
    ir_file="$TMP_DIR/$name.ll"

    "$PYTHON" "$COMPILER" "$test_file" "$ir_file" > "$TMP_OUT" 2> "$TMP_ERR"
    exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo "  FAIL $name (unexpected exit code 0)"
        FAILED=$((FAILED + 1))
        FAILED_LIST+=("invalid/$name")
    elif [ -s "$TMP_OUT" ]; then
        echo "  FAIL $name (non-empty stdout)"
        FAILED=$((FAILED + 1))
        FAILED_LIST+=("invalid/$name")
    elif [ -e "$ir_file" ]; then
        echo "  FAIL $name (output IR was created for invalid program)"
        FAILED=$((FAILED + 1))
        FAILED_LIST+=("invalid/$name")
    elif ! diff -u "$err_file" "$TMP_ERR" > "$TMP_OUT"; then
        echo "  FAIL $name (stderr mismatch)"
        cat "$TMP_OUT"
        FAILED=$((FAILED + 1))
        FAILED_LIST+=("invalid/$name")
    else
        echo "  PASS $name"
        PASSED=$((PASSED + 1))
    fi
done

echo ""
echo "═══ END-TO-END TESTS (LLVM, link, run) ═══"
if ! command -v "$CLANG" >/dev/null 2>&1; then
    echo "  FAIL: clang is required for end-to-end tests"
    FAILED=$((FAILED + 1))
    FAILED_LIST+=("clang_unavailable")
else
    for test_file in "$SCRIPT_DIR"/e2e/*.txt; do
        [ -f "$test_file" ] || continue
        name=$(basename "$test_file" .txt)
        expected_file="$SCRIPT_DIR/e2e/$name.expected"
        input_file="$SCRIPT_DIR/e2e/$name.in"
        ir_file="$TMP_DIR/$name.ll"
        bin_file="$TMP_DIR/$name"

        if ! "$PYTHON" "$COMPILER" "$test_file" "$ir_file" > "$TMP_OUT" 2> "$TMP_ERR"; then
            echo "  FAIL $name (compiler)"
            cat "$TMP_ERR"
            FAILED=$((FAILED + 1))
            FAILED_LIST+=("e2e/$name")
            continue
        fi
        if ! "$CLANG" "$ir_file" -o "$bin_file" > "$TMP_OUT" 2> "$TMP_ERR"; then
            echo "  FAIL $name (clang)"
            cat "$TMP_ERR"
            FAILED=$((FAILED + 1))
            FAILED_LIST+=("e2e/$name")
            continue
        fi
        if [ -f "$input_file" ]; then
            "$bin_file" < "$input_file" > "$TMP_OUT" 2> "$TMP_ERR"
        else
            "$bin_file" > "$TMP_OUT" 2> "$TMP_ERR"
        fi
        exit_code=$?
        expected_exit_code=0
        exitcode_file="$SCRIPT_DIR/e2e/$name.exitcode"
        if [ -f "$exitcode_file" ]; then
            expected_exit_code=$(cat "$exitcode_file")
        fi
        if [ "$exit_code" -ne "$expected_exit_code" ]; then
            echo "  FAIL $name (program exit code $exit_code, expected $expected_exit_code)"
            cat "$TMP_ERR"
            FAILED=$((FAILED + 1))
            FAILED_LIST+=("e2e/$name")
        elif ! diff -u "$expected_file" "$TMP_OUT" > "$TMP_ERR"; then
            echo "  FAIL $name (output mismatch)"
            cat "$TMP_ERR"
            FAILED=$((FAILED + 1))
            FAILED_LIST+=("e2e/$name")
        else
            echo "  PASS $name"
            PASSED=$((PASSED + 1))
        fi
    done
fi

echo ""
echo "─────────────────────────────────────"
echo "Results: $PASSED passed, $FAILED failed out of $((PASSED + FAILED)) total"

if [ $FAILED -ne 0 ]; then
    echo "Failed tests:"
    for f in "${FAILED_LIST[@]}"; do
        echo "  - $f"
    done
    exit 1
else
    echo "All tests passed! 🦆"
    exit 0
fi

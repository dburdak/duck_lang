#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPILER="$SCRIPT_DIR/../src/compiler.py"
REPO_DIR="$SCRIPT_DIR/.."

TMP_OUT=$(mktemp)
TMP_ERR=$(mktemp)
trap 'rm -f "$TMP_OUT" "$TMP_ERR"' EXIT

PASSED=0
FAILED=0
FAILED_LIST=()

echo "═══ CODE CHECKS ═══"
# Check forbidden methods/modules in src/compiler.py
FORBIDDEN_MATCHES=$(grep -nE "import re|\.split\(|\.decode\(|\.encode\(" "$COMPILER" | grep -v '\.decode("ascii")')
if [ -n "$FORBIDDEN_MATCHES" ]; then
    echo "  FAIL: Forbidden calls found in src/compiler.py:"
    echo "$FORBIDDEN_MATCHES"
    FAILED=$((FAILED + 1))
    FAILED_LIST+=("forbidden_code_check")
else
    echo "  PASS: No forbidden calls in src/compiler.py"
fi

# Check no --tokens in compiler.py or README.md
TOKENS_COMPILER=$(grep -n "\--tokens" "$COMPILER")
TOKENS_README=$(grep -n "\--tokens" "$REPO_DIR/README.md")
if [ -n "$TOKENS_COMPILER" ] || [ -n "$TOKENS_README" ]; then
    echo "  FAIL: Found --tokens references:"
    [ -n "$TOKENS_COMPILER" ] && echo "    compiler.py: $TOKENS_COMPILER"
    [ -n "$TOKENS_README" ] && echo "    README.md: $TOKENS_README"
    FAILED=$((FAILED + 1))
    FAILED_LIST+=("tokens_flag_check")
else
    echo "  PASS: No --tokens flag references"
fi

echo ""
echo "═══ VALID TESTS (happy path) ═══"
for test_file in $(ls "$SCRIPT_DIR/valid"/*.txt | sort); do
    name=$(basename "$test_file" .txt)
    expected_file="$SCRIPT_DIR/valid/$name.expected"

    python3 "$COMPILER" --ast "$test_file" > "$TMP_OUT" 2> "$TMP_ERR"
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
for test_file in $(ls "$SCRIPT_DIR/invalid"/*.txt | sort); do
    name=$(basename "$test_file" .txt)
    err_file="$SCRIPT_DIR/invalid/$name.err"

    python3 "$COMPILER" --ast "$test_file" > "$TMP_OUT" 2> "$TMP_ERR"
    exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo "  FAIL $name (unexpected exit code 0)"
        FAILED=$((FAILED + 1))
        FAILED_LIST+=("invalid/$name")
    elif [ -s "$TMP_OUT" ]; then
        echo "  FAIL $name (non-empty stdout)"
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

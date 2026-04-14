#!/bin/bash
set -e

# Test script for refdata_dependencies in wrangler spec feature.

SPEC_FILE="sample-specs/refdata-feature-demo.yaml"
REPOS_DIR="tests/temp-repos"
LOG_FILE="tests/refdata-test.log"

echo "=== Step 1: Validating Spec ==="
# Use --spec-update with --verbose to confirm validation
rm -f nb-wrangler.log
./nb-wrangler --spec-update "$SPEC_FILE" --verbose

if grep -qi "Spec validated" nb-wrangler.log; then
    echo "SUCCESS: Spec validation and update passed."
else
    echo "FAILURE: Spec validation/update failed (check nb-wrangler.log)."
    cat nb-wrangler.log
    exit 1
fi

echo "=== Step 2: Testing Data Collection (Normal) ==="
# We use --data-curate which prepares repos but only focuses on data collection
./nb-wrangler "$SPEC_FILE" --data-curate --repos-dir "$REPOS_DIR" --data-no-validation --data-no-symlinks

# Verify that DEMO_VAR exists in the output spec in the correct section
if grep -q "DEMO_VAR: \"demo_value\"" "$SPEC_FILE"; then
    echo "SUCCESS: DEMO_VAR found in output spec."
else
    echo "FAILURE: DEMO_VAR not found in output spec (check file content)."
    cat "$SPEC_FILE"
    exit 1
fi

echo "=== Step 3: Testing Data Collection with --dev ==="
./nb-wrangler "$SPEC_FILE" --data-curate --repos-dir "$REPOS_DIR" --data-no-validation --data-no-symlinks --dev

# Verify that dev overrides for refdata_dependencies were applied
if grep -q "DEMO_VAR: \"demo_dev_value\"" "$SPEC_FILE"; then
    echo "SUCCESS: Dev override for DEMO_VAR applied."
else
    echo "FAILURE: Dev override for DEMO_VAR not found."
    cat "$SPEC_FILE"
    exit 1
fi

if grep -q "NEW_DEV_VAR: \"added_in_dev\"" "$SPEC_FILE"; then
    echo "SUCCESS: NEW_DEV_VAR from dev overrides found."
else
    echo "FAILURE: NEW_DEV_VAR not found."
    exit 1
fi

echo "=== Cleaning up ==="
rm -rf "$REPOS_DIR" "$LOG_FILE"
# Reset the spec file (remove the 'out' section)
./nb-wrangler --spec-reset "$SPEC_FILE"

echo "=== All Tests Passed! ==="

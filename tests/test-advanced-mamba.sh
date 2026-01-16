#!/bin/bash

# Functional test for advanced Mamba environment definitions
set -e # Exit immediately if a command exits with a non-zero status.
set -x # Print commands and their arguments as they are executed.

# 0. Setup
TEST_DIR=$(pwd)
# export NBW_ROOT="${TEST_DIR}/build/test-advanced-mamba"
NBW_CMD="${TEST_DIR}/nb-wrangler"

# 1. Bootstrap the isolated environment (installs micromamba and base nbwrangler env)

if [ ! -d $NBW_ROOT ]; then
    # rm -rf "$NBW_ROOT"
    mkdir -p "$NBW_ROOT"
    $NBW_CMD bootstrap
fi

# Activate the bootstrapped nb-wrangler environment to put micromamba on PATH
source "$NBW_CMD" environment

echo "--- TESTING INLINE (CONCATENATED) SPEC ---"
# 2. Run curation for inline spec
$NBW_CMD sample-specs/inline-mamba-spec.yaml --curate

# 3. Verify packages for inline spec
#    - python=3.9 (base)
#    - numpy (base)
#    - click (base pip)
#    - scipy (extra mamba)
#    - toml (extra pip)

source $NBW_CMD activate inline-env-for-test

python --version | grep "3.11"
python -c "import numpy" #; print(numpy.__version__)" | grep "1.23.5"
python -c "import click"
python -c "import scipy"
python -c "import toml"

echo "--- INLINE SPEC TEST PASSED ---"

# 4. Clean up the inline environment
$NBW_CMD deactivate
$NBW_CMD sample-specs/inline-mamba-spec.yaml --env-delete

echo "--- TESTING URI (LOCAL FILE) SPEC ---"
# 5. Run curation for URI spec
$NBW_CMD sample-specs/uri-mamba-spec.yaml --curate

# 6. Verify packages for URI spec
#    - python=3.10 (base)
#    - pandas (base)
#    - rich (base pip)
#    - matplotlib (extra mamba)
#    - packaging (extra pip)
source $NBW_CMD activate shared-env-for-test

python --version | grep "3.11"
python -c "import pandas"  #; print(pandas.__version__)" | grep "1.5.3"
python -c "import rich"
python -c "import matplotlib"
python -c "import packaging"

echo "--- URI SPEC TEST PASSED ---"

# 7. Final cleanup
source $NBW_CMD deactivate
$NBW_CMD sample-specs/uri-mamba-spec.yaml --env-delete

# rm -rf "$NBW_ROOT"

echo "--- ALL ADVANCED MAMBA TESTS PASSED ---"
exit 0

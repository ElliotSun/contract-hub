#!/usr/bin/env bash
set -euo pipefail

# Example PR validation flow for ContractHub.
# This script is intentionally illustrative and expects the caller to provide
# the correct contract roots for the current pull request.

BASE_ROOT="${BASE_ROOT:-./contracts-main}"
CANDIDATE_ROOT="${CANDIDATE_ROOT:-./contracts-feature}"

echo "Running repo-level contract classification for PR validation..."
contracthub release classify-repo \
  --base-root "${BASE_ROOT}" \
  --candidate-root "${CANDIDATE_ROOT}"

echo
echo "Single-contract example:"
echo "contracthub release classify --base ./contracts/orders.main.yaml --candidate ./contracts/orders.feature.yaml"

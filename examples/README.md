# ContractHub Examples

This folder contains reference assets for wiring ContractHub into CI/CD.

## Release Assets

- `release/release-manifest.example.json`
  - example per-contract batch release manifest

## CI Shell Examples

- `ci/pr-check.example.sh`
  - single-contract and multi-contract PR build examples
- `ci/release.example.sh`
  - multi-contract release build example

## Azure DevOps Examples

- `azure-devops/contracthub-pr-validation.yml`
  - PR validation template
- `azure-devops/contracthub-release.yml`
  - release promotion template

Important rules reflected by these examples:

- version governance is per contract, not per repo
- PR builds classify changes but do not bump contract versions
- release builds apply explicit release tags only for contracts that require a bump
- contracts with `required_bump = none` are skipped by default in batch release manifests

# CHANGELOG

<!-- version list -->

## v0.5.0 (2026-05-30)

### Features

- Implement CLI prioritization and intelligent fallback for PR creation
  ([`17595e7`](https://github.com/ElliotSun/contract-hub/commit/17595e7f34969df83b2650c145fe0aa6161f6c77))


## v0.4.0 (2026-05-26)

### Features

- Add dynamic textual tui for contracthub commands
  ([`3234dd9`](https://github.com/ElliotSun/contract-hub/commit/3234dd90c6283abd348b3908fdc591e00ae558fa))

### Refactoring

- Remove Streamlit UI components and stabilize pyarrow dependency
  ([`d5a6c4e`](https://github.com/ElliotSun/contract-hub/commit/d5a6c4e15b6badfef01110369e3a041173ed6714))

- Remove Streamlit UI components to keep contracthub as a backend-only CLI
  ([`945d45d`](https://github.com/ElliotSun/contract-hub/commit/945d45d2d14173352a1bc08acc54ea26a0edaa2f))


## v0.3.0 (2026-05-21)

### Documentation

- Fix mermaid rendering errors
  ([`fd31730`](https://github.com/ElliotSun/contract-hub/commit/fd3173055622a8f6331ed0f55fc7cff37f015098))

- Optimize mermaid state diagram layout
  ([`0cd80fe`](https://github.com/ElliotSun/contract-hub/commit/0cd80fe19829051681d7f92055d9bcc7a7c56ffb))

- Simplify lifecycle state diagram to reduce clutter
  ([`a63a2af`](https://github.com/ElliotSun/contract-hub/commit/a63a2af52e14f16bac2d403204571d4b337de238))

- Use choice instead of fork in mermaid state diagram
  ([`babfc65`](https://github.com/ElliotSun/contract-hub/commit/babfc65bafe8c19422aaed183fd009fdad54d9b6))

- Use regular text node for choice box in diagram
  ([`51176c5`](https://github.com/ElliotSun/contract-hub/commit/51176c5892a9a6482731f244f96094e19738c3ea))

### Refactoring

- Rename package and installation instructions to `contracthub`
  ([`047c0f3`](https://github.com/ElliotSun/contract-hub/commit/047c0f37aba2edcd2fc33428de7b25f245cd2d4b))


## v0.2.0 (2026-05-17)

### Continuous Integration

- Enhance release workflow to support bypass tokens (GitHub App & PAT) for protected branches
  ([`88a11e2`](https://github.com/ElliotSun/contract-hub/commit/88a11e299f481e90f3da319361534e3130cee82a))

### Documentation

- Replace chinese diagram comments and states with english
  ([`aa84bb4`](https://github.com/ElliotSun/contract-hub/commit/aa84bb4ed578e9c6cf20e9a07add07514e237304))

### Features

- Support custom system and user prompt overrides in all enrichment modes
  ([`bb4846a`](https://github.com/ElliotSun/contract-hub/commit/bb4846a62e036ec33295e56afc94f0142ef2fb6a))

### Refactoring

- Add prompt overrides to enricher, fix CLI output handling, and update LLM labeling guidelines
  ([`fcca81a`](https://github.com/ElliotSun/contract-hub/commit/fcca81a2f5b5906af750288dd3c9b7889939fd37))


## v0.1.0 (2026-05-17)

- Initial Release

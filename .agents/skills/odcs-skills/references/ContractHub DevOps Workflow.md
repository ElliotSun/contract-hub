This skill defines DevOps integration behavior for ContractHub.

CONTRACT WORKFLOW

Import contract from data source

Merge with target contract

Export validation artifacts

Create PR with updates

GITOPS RULES

All contract updates must occur through pull requests.

Direct commits to main branch are not allowed.

PR CONTENT REQUIREMENTS

PR must include:

Contract diff summary

Breaking change report

Auto-deprecation summary

Schema additions list

CI/CD INTEGRATION

Merge pipeline must:

Validate ODCS schema

Run lifecycle merge dry-run

Fail on breaking changes for active contracts

AUDIT METADATA

Each merge must update:

lastMergeTimestamp
lastMergeActor
lastMergeSource

END OF SKILL
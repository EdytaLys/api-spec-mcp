---
name: spec-validator
description: Validates controller code against the approved OpenAPI spec in JIRA comments. Checks error codes, validation rules, parameters, data types, pagination, and auth. Reports discrepancies with severity levels.
version: 1.0.0
---

# Spec Validator

Validates that code implementation matches the approved OpenAPI specification posted in JIRA story comments.

## Usage

```
/spec-validator SCRUM-42 ./src/controllers/orders
```

Arguments:
1. JIRA story key
2. Path to controller/route code to validate

## What it checks

- Error response codes and body shape
- Validation rules (required fields, patterns, min/max, enums)
- Path and query parameters (names, types, defaults)
- Request body fields and types
- Response body fields and types
- Pagination parameters and response wrappers
- Authentication middleware
- Endpoint existence (spec vs code)

## Output

Posts a Jira comment with:
- Summary table (pass/fail verdict, counts)
- Discrepancy table (category, spec vs code, severity)
- Compliant endpoints list
- Versioning notes from comments
- Recommendations to fix issues

## Notes

- Uses the **latest** spec comment if multiple exist
- Severity levels: CRITICAL, WARNING, INFO
- Discrepancy types: MISSING, EXTRA, MISMATCH, NOT VERIFIED

# QA Agent Rules

> Automated testing agent. Executes /qa gstack skill with Playwright.

## Core Responsibilities

- Run Playwright tests to verify UI functionality
- Validate acceptance criteria from alignment document
- Capture screenshots on failure
- Report test results with evidence

## Three-Color Flag Rules

| Flag | Condition | Action |
|------|-----------|--------|
| 🟢 GREEN | All tests pass, no critical bugs | Proceed to deploy |
| 🟡 YELLOW | Non-critical test failures | Report to user with details |
| 🔴 RED | Critical path tests fail (login, payment) | Halt, immediate review |

## Evidence Requirements

### /qa skill
- `test_results`: Playwright JSON results
- `screenshots`: Failure screenshots (base64 or paths)
- `bugs_found`: List of bugs with severity
- `coverage_audit`: Code coverage report (optional)

## Test Execution

1. Receive test targets from Router
2. Load acceptance criteria from requirement alignment
3. Run Playwright tests: `npx playwright test --reporter=json`
4. Capture screenshots for any failures
5. Aggregate into evidence
6. Pass to checkpoint verifier

## Critical Path Tests

Always run first:
- Login/Authentication flow
- Core business logic
- Data persistence

## Performance Thresholds

- Test suite must complete within 10 minutes
- Individual test < 30 seconds
- Flag YELLOW if approaching thresholds

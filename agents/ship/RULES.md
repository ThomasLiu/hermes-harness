# Ship Agent Rules

> Deployment and release agent. Executes /ship and /land-and-deploy gstack skills.

## Core Responsibilities

- Create pull request with verified changes
- Ensure test coverage meets minimum threshold
- Execute deployment via /ship skill
- Monitor deployment health
- Rollback on failure

## Three-Color Flag Rules

| Flag | Condition | Action |
|------|-----------|--------|
| 🟢 GREEN | All checks pass, coverage > 80% | Proceed with deploy |
| 🟡 YELLOW | Coverage 60-80%, minor issues | Await human confirmation |
| 🔴 RED | Coverage < 60%, or critical bugs | Block deploy, flag human |

## Evidence Requirements

### /ship skill
- `test_results`: All tests passing
- `coverage_audit`: Coverage report showing > 80%
- `pr_url`: GitHub PR URL
- `deployment_target`: Target environment (staging/prod)

## Pre-Deploy Checklist

- [ ] All checkpoint verifications passed
- [ ] Coverage audit > 80% (or approved exemption)
- [ ] PR approved by at least 1 reviewer
- [ ] No critical bugs in bug tracker
- [ ] Rollback plan documented

## Deployment Process

1. Receive deploy signal from Router
2. Verify all checkpoints green
3. Run final test suite
4. Create/update PR
5. Request review
6. On approval: execute /ship
7. Monitor health checks
8. Record to deploy_history.jsonl
9. On failure: trigger rollback flow

## Rollback Triggers

- Health check failures > 3 consecutive
- Error rate > 5% in first 5 minutes
- Manual trigger via `hg rollback`

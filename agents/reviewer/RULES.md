# Reviewer Agent Rules

> Code review + security review agent. Executes /review and /cso gstack skills.

## Core Responsibilities

- Review code changes for correctness, style, and security
- Run tsc/type checking independently (not trusting skill self-report)
- Identify Critical/High severity security vulnerabilities via /cso
- Report findings with evidence

## Three-Color Flag Rules

| Flag | Condition | Action |
|------|-----------|--------|
| 🟢 GREEN | All checks pass, no high-severity findings | Proceed autonomously |
| 🟡 YELLOW | Medium-severity issues found | Report to user, await confirmation |
| 🔴 RED | Critical security vulnerabilities (OWASP A01-A10) | Halt, immediate human review |

## Evidence Requirements

### /review skill
- `tsc_output`: TypeScript compiler output (must have 0 errors)
- `diff_summary`: Lines added/removed (e.g. "+100 -20")
- `findings`: List of code issues found

### /cso skill
- `owasp_findings`: OWASP Top 10 findings
- `stride_model`: STRIDE threat model results
- `severity_summary`: {critical: N, high: N, medium: N, low: N}
- `exploit_scenarios`: Potential attack vectors

## Large File Rule

Files > 200 LOC must be split before review. Flag as YELLOW if encountered.

## Review Process

1. Receive diff/code from Router
2. Run tsc independently (`npx tsc --noEmit --json`)
3. Execute /review gstack skill
4. Execute /cso if security-sensitive path
5. Aggregate findings into evidence
6. Pass to checkpoint verifier
7. Report three-color flag decision

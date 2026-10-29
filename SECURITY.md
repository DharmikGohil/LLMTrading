# Security policy

This code places orders. Treat these as security issues and report them privately:

- anything that can send an unintended order, bypass a risk limit, the kill switch or the paper/live switch
- broken or skipped stop-loss handling
- leaked credentials (broker keys, API keys, tokens) anywhere in the repository or its history
- injection paths from external text (news, filings, LLM output) into orders

## Reporting

Use GitHub's private reporting: **Security → Report a vulnerability** on this repository. If that is not
available, open an issue that says only "security contact needed" (no details) and the maintainer will
reach out. Expect an acknowledgement within a few days.

## Supported versions

Only `main` is supported.

## Handling secrets

Keys belong in `.env` (git-ignored) or the environment. If a key is ever committed, revoke it at the provider
first, then remove it from the history.

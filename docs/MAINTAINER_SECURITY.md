# Repository security and privacy controls

Configure these controls in the GitHub UI for `dward239/sof_app`.

1. **Settings → Rules → Rulesets:** Create an active ruleset for `main`. Block deletion and force pushes; require pull requests and successful checks before merge. Choose the actual status names from a successful workflow run, including `test-build (3.10)`, `test-build (3.11)`, `test-build (3.12)` and `privacy`. If you are the only reviewer, avoid a mandatory approval rule that prevents your own merges.
2. **Settings → Security / Advanced Security:** Enable the dependency graph, Dependabot alerts and any available secret scanning and push protection features. Verify their status manually. The committed Dependabot file schedules monthly dependency-update PRs; it does not activate all repository security settings.
3. **GitHub account Settings → Emails:** Enable email privacy, obtain your actual `...@users.noreply.github.com` address and block pushes exposing a personal email if available.
4. **Local Git identity:** Configure your computer before future commits:

```powershell
git config --global user.name "dward239"
git config --global user.email "YOUR_GITHUB_NOREPLY_ADDRESS"
git config --show-origin --get user.name
git config --show-origin --get user.email
git config --local --get-regexp '^user\.'  # Check for local overrides
```

Git commit identity cannot be altered retroactively through settings alone. The first commits in this clean repository still include an author **name** from the connected GitHub account, although they use the private GitHub **email**. If suppressing that name matters, regenerate the new repository's tiny history with an explicit author identity, and account for forks/caches.

## Before a public release

- Require the Windows CI and privacy checks to pass for the exact release commit.
- Independently verify the engineering calculations and input assumptions.
- Scan binaries/archives for embedded usernames, local paths, signing keys, or other metadata.
- Review dependency alerts, applicable Qt licensing and other third-party licenses.
- Publish vetted hashes and release provenance, and keep confidential inventories out of public discussions.

The text privacy scanner is preventative. It does not cover historical Git objects, private data inside binary artifacts, uploaded attachments, or externally mirrored copies.

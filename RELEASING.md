# Releasing ComplianceAgent

Two one-time manual setups unlock automated distribution. They cannot be done
from CI — they require a maintainer logged in to PyPI and GitHub. Do them once,
then every release is `git tag vX.Y.Z && git push --tags`.

## 1. PyPI Trusted Publishing (OIDC) — required before the first automated publish

`.github/workflows/publish.yml` publishes with **Trusted Publishing** (OIDC), so
no PyPI API token is stored in the repo. PyPI must be told to trust this
workflow first, or every `publish` run fails at the upload step with
`invalid-publisher`.

1. Sign in at <https://pypi.org>.
2. **First release only** (project does not exist yet): go to
   <https://pypi.org/manage/account/publishing/> and add a *pending* publisher.
   For an existing project: **Your projects → compliance-agent → Manage →
   Publishing → Add a new publisher**.
3. Choose **GitHub Actions** and enter exactly:
   - **Owner**: `latreon`
   - **Repository**: `compliance-agent`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`
4. Save. The `environment: pypi` in the publish job must match this value.

(Optional but recommended: also configure the same publisher on
<https://test.pypi.org> for dry runs.)

### Cut a release

1. Bump `__version__` in `src/compliance_agent/__init__.py` and update
   `CHANGELOG.md`.
2. `git commit`, then `git tag vX.Y.Z && git push origin main --tags`.
3. The `Publish` workflow verifies the tag matches `__version__`, builds, checks
   the wheel + metadata, publishes to PyPI via OIDC, and creates a GitHub
   release.

## 2. GitHub Marketplace listing — the primary distribution channel

`action.yml` makes the repo a composite GitHub Action, but it is not discoverable
until it is **published to the Marketplace**. Developers searching "EU AI Act"
in the Marketplace find nothing until this is done.

1. Ensure `action.yml` has a unique `name` and a `branding` block (icon +
   color) — the Marketplace requires branding to publish. (Present in this repo.)
2. Push a release tag (`vX.Y.Z`) — Marketplace listings are tied to a release.
3. On GitHub: **Releases → Draft/Edit the release for the tag**. GitHub shows a
   **"Publish this Action to the GitHub Marketplace"** checkbox — tick it.
4. Accept the Marketplace Developer Agreement (first time only), pick primary +
   secondary categories (e.g. **Code quality**, **Security**), and publish.
5. Verify the listing appears at
   `https://github.com/marketplace/actions/<action-name>` and that
   `uses: latreon/compliance-agent@v0` resolves.

Keep a moving major tag (`v0`) pointing at the latest release so consumers can
pin `@v0`:

```bash
git tag -f v0 vX.Y.Z && git push -f origin v0
```

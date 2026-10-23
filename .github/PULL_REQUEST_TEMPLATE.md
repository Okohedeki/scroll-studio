## What and why

<!-- What this changes, and why. Link the issue: "Closes #123". -->

## How I checked it

<!-- Tests you added or ran, examples you built, and pictures or a short recording for anything visual. -->

## Checklist

- [ ] It is an engine feature or fix, not a one-off page ([ground rules](../CONTRIBUTING.md#ground-rules)); no hosted APIs or keys.
- [ ] Tests added or updated; `python -m pytest -q` passes locally.
- [ ] Layout snapshots unchanged, or re-recorded on purpose and explained above.
- [ ] Themes and styles keep the [consistency rules](../CONTRIBUTING.md#consistency-rules) (`tests/test_conformance.py`).
- [ ] `runtime/src` changed: `npm run build:runtime` run and the bundle committed.
- [ ] Docs and a `CHANGELOG.md` line under `## Unreleased`, if a user would notice.
- [ ] New dependencies declared (`pyproject.toml`, `runtime/package.json`, `engine/models.yaml`, `docs/INSTALL.md`).
- [ ] Third-party material (code, images, models, text) named with its source and licence.
- [ ] I have signed, or will sign, the [CLA](../CLA.md).

# Releasing

How a version of Scroll Studio is released. Versions follow [semantic versioning](../compatibility.md); a minor
release usually closes a milestone.

## Before

- [ ] The milestone's issues are closed or moved to the next milestone.
- [ ] `main` is green: every required check, plus the platform jobs (Windows, macOS).
- [ ] The GPU quality suite has run on `main` and its contact sheets look right (once dedicated compute exists,
  [#70](https://github.com/Okohedeki/scroll-studio/issues/70)); until then, build two or three examples on a GPU
  machine and look at them with `studio snapshot`.
- [ ] Every `breaking-change` and `deprecated` fragment has a migration note, and the migration guide in the docs is
  updated for a major release.
- [ ] `docs/whats-new.md` describes the release for people, with pictures.
- [ ] The showcase builds with the release candidate.

## Prepare the release pull request

```bash
pip install towncrier==26.9.0
git switch main && git pull
python tools/release.py prepare 1.5.0
```

This sets the version in `pyproject.toml` and gathers the fragments in `changes/` into a new section of
`CHANGELOG.md` (deleting them). Read the section: edit it into good prose if it helps, and keep every migration note.
Then commit on a branch `release/v1.5.0` with the title `chore(release): 1.5.0`, open a pull request labelled
`release` (the policy check skips release pull requests), and merge it when green.

For a release candidate, use a version like `1.5.0rc1`; the release is marked as a pre-release.

## Tag

After the release pull request is merged, tag the merge commit on `main` and push the tag. Only administrators can
push `v*` tags (the "Release tags" ruleset).

```bash
git switch main && git pull
git tag -a v1.5.0 -m "Scroll Studio 1.5.0"     # -s instead of -a if you sign tags
git push origin v1.5.0
```

The [release workflow](https://github.com/Okohedeki/scroll-studio/blob/main/.github/workflows/release.yml) then:

1. checks the tag matches `pyproject.toml`;
2. builds the sdist and wheel;
3. writes an SPDX SBOM (`scroll-studio.spdx.json`);
4. attests build provenance for the packages, so anyone can check where they came from:
   `gh attestation verify scroll_studio-1.5.0-py3-none-any.whl --repo Okohedeki/scroll-studio`;
5. creates the GitHub release with the changelog section, the packages and the SBOM;
6. publishes to PyPI, once that is set up (below).

## After

- [ ] Close the milestone; move anything left to the next one.
- [ ] Post in Discussions → Announcements with the highlights and a link to the release.
- [ ] Update the showcase and the docs site's version list.
- [ ] Update the supported versions in [SECURITY.md](https://github.com/Okohedeki/scroll-studio/blob/main/SECURITY.md).

## Setting up PyPI (once)

1. Create the `scroll-studio` project on PyPI with a trusted publisher: owner `Okohedeki`, repository
   `scroll-studio`, workflow `release.yml`, environment `pypi`.
2. In the repository settings, create the environment `pypi` (optionally requiring a maintainer's approval) and set
   the repository variable `PYPI_PUBLISH` to `true`.

No token is stored anywhere: PyPI trusts the workflow's identity.

## A security release

Follow [SECURITY.md](https://github.com/Okohedeki/scroll-studio/blob/main/SECURITY.md#for-maintainers): fix in the
advisory's private fork, then release a patch version as above, then publish the advisory.

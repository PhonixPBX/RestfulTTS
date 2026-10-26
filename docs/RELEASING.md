# Releasing RestfulTTS

Versions follow [Semantic Versioning](https://semver.org/) in PEP 440 form: `1.2.0`, `1.2.0rc1`, `1.3.0.dev0`.
Pushing a tag `v<version>` starts `container.yml`, which:

1. runs `scripts/release.sh check <tag>`; it fails if the tag, the version files and `CHANGELOG.md` disagree
2. builds the image and runs the smoke test (`scripts/test-container.sh`)
3. pushes `ghcr.io/<owner>/restfultts:<version>` for linux/amd64 and linux/arm64, plus `latest` for final releases
4. creates the GitHub release with the `CHANGELOG.md` section as release notes

A tag with a pre-release suffix (`v1.2.0rc1`) becomes a GitHub pre-release, and its image gets only its version
tag, never `latest`.

Between releases, `container.yml` builds the default branch every night if it has new commits, and pushes it as
`edge` and `sha-<short>`. A manual run (*Actions → container → Run workflow*) does the same at any time.

## Before the release

- CI is green on `main`.
- `uv run pytest -m models` passes. This is real synthesis in all four languages and is not part of CI.
- The `## [Unreleased]` section of `CHANGELOG.md` lists every user-visible change.

## Release

1. Set the version in `pyproject.toml` and `src/restfultts/__init__.py`, then run `uv lock` (the lock file records
   the project version).
2. Rename `## [Unreleased]` in `CHANGELOG.md` to `## [X.Y.Z] - YYYY-MM-DD` and add the compare link at the bottom:

   ```
   [X.Y.Z]: https://github.com/<owner>/RestfulTTS/compare/vX.Y.(Z-1)...vX.Y.Z
   ```

   For the first release, link `https://github.com/<owner>/RestfulTTS/releases/tag/v0.1.0` instead.
3. Check with `scripts/release.sh check vX.Y.Z` and `scripts/release.sh notes vX.Y.Z`.
4. Commit with `release: X.Y.Z` and push to `main`. Wait until CI is green for this commit.
5. Tag and push the tag:

   ```sh
   git tag -s vX.Y.Z -m "RestfulTTS X.Y.Z"
   git push origin vX.Y.Z
   ```

6. Check the GitHub release and the ghcr.io tags.

## After the release

Start the next development version with a commit `release: start X.Y+1.0 development`:

- set `X.Y+1.0.dev0` in both version files and run `uv lock`
- add an empty `## [Unreleased]` section to `CHANGELOG.md`

## First release

A newly pushed ghcr.io package is private. Make it public once under *Package settings → Change visibility*, so
that PhonixPBX hosts can pull it without logging in.

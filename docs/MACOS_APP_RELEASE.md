# macOS app release

AudioAtlas ships one analysis engine in two interfaces. The Python wheel is the
advanced interface; `AudioAtlas.app` is the one-track Apple Silicon interface.

## Local beta build

On an Apple Silicon Mac with Python 3.11 and `uv`:

```bash
uv sync --locked --extra dev --extra app-build
uv run python scripts/build_macos_app.py
dist/macos/AudioAtlas.app/Contents/MacOS/AudioAtlas \
  --smoke-analyze tests/fixtures/sine_1k_-6dbfs_2s.wav \
  --output-parent /tmp/audioatlas-app-smoke
codesign --verify --deep --strict --verbose=2 dist/macos/AudioAtlas.app
```

The `macOS app` workflow repeats this build and smoke, enforces a 275 MiB
installed / 110 MiB compressed ceiling, and uploads an ad-hoc-signed ZIP for
owner testing. Do not present that artifact as the friend-ready download.

## Private friend demo candidate

Run `macOS Demo Candidate` manually from the committed `main` branch. It uses
the protected signing environment but has read-only repository permissions and
cannot create a release or publish a Python package. The workflow produces a
14-day private artifact containing the signed, notarized, stapled DMG and a ZIP
with the authorized project demo track, checksums, candidate manifest, rights
notice, and fillable clean-Mac guide.

Download the complete kit through a browser before testing so the handoff keeps
normal quarantine behavior. Do not substitute the ad-hoc beta ZIP or bypass
Gatekeeper. A missing signing or notarization secret fails the candidate build;
there is no friend-facing unsigned fallback.

## GitHub environment and secrets

Create the protected `macos-release` environment and configure:

- `MACOS_CERTIFICATE_P12`: base64-encoded Developer ID Application certificate;
- `MACOS_CERTIFICATE_PASSWORD`: password for that PKCS#12 file;
- `MACOS_SIGNING_IDENTITY`: exact Developer ID Application identity;
- `MACOS_TEAM_ID`: expected Developer ID team identifier;
- `APPLE_API_KEY_P8`: base64-encoded App Store Connect API private key;
- `APPLE_API_KEY_ID`: API key identifier;
- `APPLE_API_ISSUER_ID`: API issuer identifier.

The candidate and tagged release workflows import the certificate into an ephemeral keychain,
builds and verifies the signed app, creates and signs the DMG, submits it with
`notarytool`, waits for acceptance, staples and validates the ticket, performs a
Gatekeeper assessment, and attaches the DMG plus checksum to the draft GitHub
prerelease. It verifies every Mach-O is arm64-compatible and requires no newer
than macOS 14, rejects unresolved non-system libraries, retrieves and audits the
notarization log even after acceptance, and removes ephemeral credentials in an
unconditional cleanup step. It does not log secret material.
Both workflows invoke `scripts/package_macos_dmg.py` so DMG contents, identity,
notarization, stapling, Gatekeeper, size, checksum, and manifest audits cannot
drift between the private rehearsal and the tagged release.

## Human release gate

Create a protected `macos-acceptance` environment with required reviewers.
Before approving that gate, test the candidate on a separate Apple Silicon
macOS 14-or-newer account:

1. Download the DMG and drag AudioAtlas to Applications.
2. Launch normally without a Gatekeeper bypass.
3. Analyze by file chooser and window drop, including a path with spaces and
   Unicode.
4. Confirm progress, the adjacent report folder, automatic browser opening,
   Finder reveal, rerun behavior, safe cancellation, and a corrupt-file error.
5. Confirm an unwritable source location offers another report destination.
6. Confirm same-stem files with different extensions do not replace one another.
7. Test a fresh install, upgrade, duplicate copy, launch from the mounted DMG,
   and launch after copying to Applications.
8. Disconnect networking and confirm an installed app still produces a report.

Record install actions, time to first report, hesitations, and any explanation
the tester needed in the included `DEMO_AND_ACCEPTANCE_GUIDE.md`. Retain the
completed record with the release notes or tracking issue before approving the
environment. Intel and Windows desktop packages require their own clean
machine, packaging, signing, and friend-use gates.

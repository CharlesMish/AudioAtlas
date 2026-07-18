# AudioAtlas Internal Windows Candidate

This kit is an **unsigned internal test candidate**, not a friend-ready public
download. Windows may block it because it has no trusted publisher reputation.
Do not disable or bypass Windows security controls. Record any block as the
remaining signing or Store-distribution gate.

AudioAtlas analyzes one local file and writes a static report beside that file
or in a folder you select. Audio is not uploaded, and the app has no telemetry,
account, updater, or network requirement after download.

## Candidate record

- Candidate ID:
- Manifest SHA-256:
- Tester:
- Date:
- PC model:
- CPU architecture:
- Windows edition and exact build:
- Standard/non-administrator account confirmed:
- Security or reputation result:
- UI-ready time:
- First demo-report time:
- First user-report time:

## Files

- `*-portable.zip`: unpack and run `AudioAtlas.exe`; no installation is performed.
- `*-setup.exe`: per-user installer; it must not request administrator access.
- `windows-candidate-manifest.json`: build identity and artifact hashes.
- `windows-pe-audit.json`: packaged executable and DLL closure.
- `THIRD_PARTY_LICENSES.txt`: packaged dependency notices.
- `SHA256SUMS.txt`: hashes for the executable artifacts, evidence, and demo audio.
- `audioatlas_demo.wav`: AudioAtlas project-demo material governed by `AUDIO_RIGHTS.md`.

Verify the hashes before testing. Do not continue if a file does not match.

## Functional checklist

- [ ] Portable copy opens without Python, PowerShell, administrator access, or network.
- [ ] Fresh per-user installation and normal launch succeed.
- [ ] Replacement installation succeeds and keeps external reports.
- [ ] A duplicate portable copy behaves independently.
- [ ] Offline relaunch succeeds.
- [ ] File picker analyzes `audioatlas_demo.wav`.
- [ ] File picker analyzes one user-selected track.
- [ ] Spaces, Unicode, and a long source path succeed.
- [ ] Cancel during preparation and analysis leaves the previous report unchanged.
- [ ] Close during analysis waits for safe cleanup, then relaunch succeeds.
- [ ] Same-stem inputs choose separate owned report folders.
- [ ] Malformed input shows a short error without a traceback.
- [ ] Read-only/unavailable output offers another location before analysis.
- [ ] Open Report, Show Report in Explorer, and Open Troubleshooting Log work.
- [ ] Upgrade and uninstall do not remove reports outside the installation directory.
- [ ] Uninstall removes the installed application without requiring manual cleanup.

## Acceptance result

- Engineering acceptance: PASS / FAIL
- Windows 10 22H2 compatibility evidence: PASS / FAIL / BLOCKED
- Windows 11 compatibility evidence: PASS / FAIL / BLOCKED
- Friend-ready distribution: **BLOCKED until signed/Store security acceptance passes**
- Notes and retained log location:

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
- Browser-downloaded kit filename:
- Kit SHA-256 result:
- UI-ready time:
- First demo-report time:
- First user-report time:

## Files

- `*-installer-test-kit.zip`: primary test kit for Windows 11, then Windows 10.
- `*-portable-test-kit.zip`: separate secondary no-install test kit.
- `*.zip.sha256`: expected hash for its adjacent test kit.
- `README_FIRST.txt`: identifies the installer-first testing path.
- `*-portable.zip`: inside the portable kit; unpack and run `AudioAtlas.exe`.
- `*-setup.exe`: inside the installer kit; per-user and must not request administrator access.
- `windows-candidate-manifest.json`: build identity and artifact hashes.
- `windows-pe-audit.json`: packaged executable and DLL closure.
- `THIRD_PARTY_LICENSES.txt`: packaged dependency notices.
- `SHA256SUMS.txt`: hashes for the executable artifacts, evidence, and demo audio.
- `audioatlas_demo.wav`: AudioAtlas project-demo material governed by `AUDIO_RIGHTS.md`.

## Start here: installer test

1. On Windows 11, download the installer-test artifact in a web browser and
   extract the outer GitHub artifact ZIP normally.
2. In PowerShell, change to that extracted folder and compare the two values:

   ```powershell
   Get-FileHash -Algorithm SHA256 .\AudioAtlas-*-installer-test-kit.zip
   Get-Content .\AudioAtlas-*-installer-test-kit.zip.sha256
   ```

3. Stop if the hashes differ. Extract the verified installer-test-kit ZIP,
   read this guide from inside it, then launch the setup executable normally.
4. The installer must use the current account, must default to
   `%LOCALAPPDATA%\Programs\AudioAtlas`, and must not request administrator access.
5. Complete Windows 11 acceptance before downloading and testing the identical
   candidate on Windows 10 22H2.

For the secondary portable kit, use the same commands with
`portable-test-kit.zip`. After extracting that kit, verify its `SHA256SUMS.txt`
entries with `Get-FileHash` before extracting the inner portable ZIP. Do not
continue if any value differs.

## Functional checklist

- [ ] Portable copy opens without Python, PowerShell, administrator access, or network.
- [ ] Installer kit was downloaded in a browser and its adjacent SHA-256 matched.
- [ ] Fresh per-user installation and normal launch succeed.
- [ ] Installation used `%LOCALAPPDATA%\Programs\AudioAtlas` and showed no elevation prompt.
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
- Windows 11 compatibility evidence: PASS / FAIL / BLOCKED
- Windows 10 22H2 compatibility evidence: PASS / FAIL / BLOCKED
- Friend-ready distribution: **BLOCKED until signed/Store security acceptance passes**
- Notes and retained log location:

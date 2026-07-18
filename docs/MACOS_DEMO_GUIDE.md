# AudioAtlas macOS demo and acceptance guide

This private kit is for demonstrating AudioAtlas on an Apple Silicon Mac running
macOS 14 or newer. AudioAtlas analyzes one local audio file at a time. It does
not upload audio, require an account, or use telemetry.

## Install and make the first report

1. Download this complete ZIP through a web browser and extract it with macOS.
2. Compare the DMG checksum with `SHA256SUMS.txt`.
3. Open the DMG. Do not bypass or disable macOS security checks.
4. Drag AudioAtlas to Applications, then open it normally from Applications.
5. Drag `audioatlas_demo.wav` onto the window or use **Choose Audio File**.
6. Allow extra time for **Starting the local analysis engine…** on the first run.

The report is written beside the source as
`AudioAtlas Report – audioatlas_demo` and opens in the default browser. AudioAtlas
can instead prompt for a writable report location. **Show Report in Finder**
remains available after a successful run.

For an unexpected failure, choose **Open Troubleshooting Log**. The local log is
`~/Library/Logs/AudioAtlas/app.log`; it is never transmitted automatically.

To uninstall, quit AudioAtlas and move `AudioAtlas.app` from Applications to the
Trash. Reports remain where they were created. Optional caches and logs are in
`~/Library/Caches/AudioAtlas` and `~/Library/Logs/AudioAtlas`.

The included recording is project-demo material governed by `AUDIO_RIGHTS.md`.
It is not a general-purpose stock music asset.

## Clean-Mac acceptance record

Candidate ID: ____________________  Date: __________  Tester: _______________

Mac model: _______________________  Apple chip: _____________________________

macOS version: ___________________  Internet disconnected test: yes / no

Cold launch time: _______________  First report time: ______________________

- [ ] The kit was downloaded through a browser and extracted normally.
- [ ] The DMG checksum matched and macOS accepted it without a security bypass.
- [ ] AudioAtlas launched directly from the mounted DMG.
- [ ] AudioAtlas copied to Applications and launched normally.
- [ ] Fresh install, replacement install, and a duplicate copy were exercised.
- [ ] The stapled app launched and analyzed audio while offline.
- [ ] File picker and drag-and-drop each accepted one track.
- [ ] The included demo and one tester-selected track produced complete reports.
- [ ] A source path containing spaces and Unicode produced a complete report.
- [ ] Cancel during analysis left the previous report unchanged.
- [ ] Quit during analysis completed a safe stop and the app relaunched normally.
- [ ] Rerun and same-stem/different-extension inputs used safe report folders.
- [ ] Malformed input showed an actionable message without a traceback.
- [ ] A read-only source location prompted for another report location.
- [ ] Browser opening, Show Report in Finder, and Open Troubleshooting Log worked.
- [ ] No Python, Terminal, administrator access, account, or post-download network
      connection was required.

Result: PASS / FAIL

Notes and failure-log location:

______________________________________________________________________________

Retain this completed record with the release notes or release-tracking issue
before approving the protected `macos-acceptance` environment for a tagged
release.

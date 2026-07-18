# Windows Desktop Candidate Packaging

Pass Two Phase B implements a private Windows engineering candidate. It does
not advertise or publicly distribute a friend-ready Windows executable.

## Target and evidence

The intended client targets are Windows 10 22H2 x64 and Windows 11 x64. Windows
11 is recommended. Windows 10 compatibility is useful for the owner's Ableton
machine, but Windows 10 reached end of ordinary Microsoft support in October
2025; AudioAtlas compatibility must never be presented as operating-system
security support. Earlier Windows 10 versions, 32-bit Windows, and Windows
ARM64 are out of scope.

`windows-latest` CI proves the shared Python, Win32, and NTFS contracts. It does
not reproduce Explorer, SmartScreen, quarantine/download, or installation on a
Windows 10 client. A future package cannot claim Windows 10 support until it is
rehearsed on the actual Windows 10 Ableton machine.

Cross-platform summary comparison requires the same keys, shapes, schemas,
graph identities, and finding identities. Exact environment hashes will differ.
Floating-point measurements use the tolerances already declared by their
fixture tests; presentation files and serialized structure may not silently
diverge.

## Desktop adapter

The Tkinter UI consumes `DesktopRunController` and marshals worker callbacks
through a queue polled on Tk's event thread. The adapter owns file selection,
progress controls, native confirmation, opening the browser, revealing
reports/logs, and deferred close. It does not duplicate inspection, worker,
retry, cancellation, or report-state logic. Drag-and-drop remains deferred.

## Candidate forms

The workflow builds an x64 Python 3.11 PyInstaller onedir application, then
packages that exact directory as both a portable ZIP and an Inno Setup per-user
installer. The installer needs neither administrator access nor writes beside
user audio. Runtime caches/logs use standard per-user directories and analysis
remains fully offline.

The workflow artifacts are private, retained for 14 days, and labeled
`INTERNAL`. Code signing is not required for development, but unsigned output
cannot satisfy friend-ready acceptance. Documentation explains ordinary
SmartScreen behavior without instructing users to weaken or bypass security.

Every frozen candidate audits architecture, Python and native dependencies,
the Visual C++ runtime, unresolved DLLs, executable inventory, activation-size
budgets, and packaged license notices.
No service, registry integration, shell extension, automatic network request,
or elevation is part of the initial package.

## Acceptance for the packaging pass

Test portable and installed candidates on clean Windows 11 and the actual
Windows 10 22H2 x64 machine. Cover fresh install, replacement install, duplicate
copy, uninstall, offline relaunch, Unicode/spaces and long source paths, local
and read-only destinations, malformed input, cancellation/close during every
phase, same-stem collisions, prior-report preservation, browser opening, report
reveal, and troubleshooting-log access.

Acceptance requires no Python, Terminal/PowerShell, administrator access,
security bypass, network connection after download, raw traceback, missing DLL,
or damage to an earlier report.

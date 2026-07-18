# Future Windows Desktop Packaging

This document defines the boundary for a later Windows packaging pass. Pass Two
does not build, advertise, or distribute a Windows desktop executable.

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

A Windows UI will consume `DesktopRunController` and marshal worker callbacks
onto its native event thread. The toolkit remains deliberately undecided until
the Cocoa adapter and headless controller tests prove that this boundary is
complete. The adapter may own file selection/drop, progress controls, native
confirmation, opening the browser, revealing reports/logs, and deferred close.
It must not duplicate inspection, worker, retry, cancellation, or report-state
logic.

## Candidate forms

The first internal artifact should be portable and unpackable without an
installer. The friend-facing candidate should then use a per-user installer
that needs neither administrator access nor writes beside the installed app.
It must use standard per-user cache/log directories and remain fully offline
after download.

Code signing is desirable for friend distribution and reputation building but
is not required for local development. Unsigned artifacts must be labeled
internal-only. Documentation must explain ordinary SmartScreen behavior without
instructing users to weaken security or bypass system protections.

Every frozen candidate must audit architecture, Python and native dependencies,
the Visual C++ runtime, unresolved DLLs, and the packaged license inventory.
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

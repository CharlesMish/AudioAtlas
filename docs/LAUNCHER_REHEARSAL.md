# AudioAtlas Native Launcher Rehearsal

CI verifies the Python CLI on macOS and Windows runners. That does **not** prove
that Finder/Explorer double-click launchers work for a nontechnical person on a
clean machine. This document defines the native evidence needed before stronger
ease-of-use claims.

## What counts as a rehearsal

A rehearsal occurs on the target operating system through the normal graphical
shell, not by invoking the script from an already configured developer terminal.
Record the actual installation state, security prompts, PATH behavior, filenames,
and result.

Static inspection and Linux execution of `.command` files do not count as a
macOS rehearsal. CI PowerShell/cmd invocation does not count as a Windows
Explorer double-click rehearsal.

## Minimum matrix

Run at least one clean or newly created user account on each target:

| Platform | Required context |
|---|---|
| macOS | supported macOS release; Apple Silicon when available; Finder double-click; Gatekeeper state recorded |
| Windows | supported Windows release; Explorer double-click; SmartScreen/security state recorded |

Useful additional coverage:

- machine with Python installed but console-script PATH not inherited by GUI;
- project path containing spaces;
- source filename containing spaces and non-ASCII characters;
- standard user without administrator privileges;
- lossless WAV plus one locally supported compressed format.

## Test sequence

1. **Installation truth**
   - Record exactly how AudioAtlas was installed.
   - Confirm `audioatlas --version` in the intended environment.
   - Do not silently repair PATH before recording the initial state.

2. **Empty input behavior**
   - Double-click the launcher with no audio present.
   - Confirm the message explains what to do and the window remains readable.

3. **One ordinary file**
   - Use a short authorized WAV.
   - Confirm the launcher identifies the file, creates the expected report, and
     opens or clearly points to `report.html`.

4. **Spaces and Unicode**
   - Place the kit and audio under names containing spaces.
   - Use a filename containing at least one non-ASCII character.
   - Confirm no truncation, mojibake, or path splitting.

5. **Multiple-file selection**
   - Put at least two supported files in `PUT_AUDIO_HERE`.
   - Confirm selection is understandable and invalid input fails safely.

6. **Corrupt/unsupported input**
   - Include one corrupt supported-extension file and one unsupported file.
   - Confirm the message is readable, local paths are not exposed unnecessarily,
     and prior good reports remain intact.

7. **Rerun behavior**
   - Add an unrelated note file to the output folder.
   - Rerun the same report and then a different graph profile.
   - Confirm AudioAtlas updates owned files, removes stale owned plots, and
     preserves the unrelated file.

8. **Security and close behavior**
   - Record Gatekeeper, quarantine, SmartScreen, antivirus, or execution-policy
     prompts verbatim in the log.
   - Confirm the result/error remains visible before the terminal window closes.

## Acceptance levels

- **CLI supported:** command-line workflow succeeds; no native launcher claim.
- **Launcher rehearsed:** the sequence above succeeds on one named OS/context,
  with observed caveats documented.
- **Nontechnical setup candidate:** a fresh user can install and run without a
  developer terminal after a separate installation/package design has been
  tested. The current launcher kit does not claim this level.

One successful machine does not establish universal platform support. Report the
specific environment and preserve failures.

## Recording

Use `starter_kit/LAUNCHER_REHEARSAL_LOG.md` for each run. Attach screenshots only
when they do not disclose private paths or personal information. Record failures
before applying fixes so the evidence does not become a polished reconstruction.

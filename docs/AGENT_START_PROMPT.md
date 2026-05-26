# Suggested first prompt for Codex / Grok Build

Use this prompt when you hand the repo to an agent for the first feature
slice. Replace the task section if you want a different ticket.

```text
You are working on AudioAtlas, a local single-track audio analysis tool for
music production, mixing, mastering, and deep listening.

Before coding:
1. Read AGENT_BRIEF.md.
2. Read docs/ARCHITECTURE.md.
3. Read docs/AGENT_TASKS.md.
4. Run make test.
5. Do not change product scope without asking.

Core product framing:
AudioAtlas is a "song microscope." It produces measured facts and visual maps
for one audio file. It does not judge the mix, score it, compare it to
references, or give mastering advice.

Hard constraints:
- Preserve original audio levels. Do not auto-normalize.
- Internal audio shape is always (n_samples, n_channels).
- Analysis functions take arrays and return dataclasses.
- Visualization functions render existing analysis results and do not recompute analysis.
- The CLI stays thin.
- Add tests for every new analysis function.
- No reference-track comparison.
- No mix-health score.
- No AI-generated mastering advice.
- No Streamlit/HTML/PDF until explicitly assigned.
- Names must be honest: RMS is not loudness; centroid is not "brightness" unless described carefully.

Important note:
Do not start with T-001 true-peak refinement unless explicitly assigned. That
is subtle DSP work. Start with T-002 stereo correlation timeline unless I say
otherwise.

Recommended first task:
Implement T-002 — Stereo correlation timeline.

Acceptance discipline:
- Add a result dataclass.
- Add a pure compute function.
- Add synthetic tests.
- Add a visualization function.
- Add summary.json entry.
- Add report.md section.
- Wire it into pipeline.py.
- Update docs/SUMMARY_SCHEMA.md and docs/CHANGELOG.md.
- Run make check before reporting done.

Before implementing, briefly summarize:
1. Which files you will touch.
2. What tests you will add.
3. What output file will be generated.
4. Any DSP assumptions you are making.
```

# AudioAtlas — Product / UX / Report-Language Review

Reviewer: Claude (Anthropic)
Scope: REVIEW_PROMPT.md + calibration_context.md + AUDIT.md + SUMMARY_SCHEMA.md + design/report_mockup.html + 14 calibration report folders.
Constraint respected: no Python, no implementation. Conceptual/spec output only.

---

## 0. Executive summary

AudioAtlas already does the hardest thing right: it measures, it doesn't judge. The DSP is honest, the layering is clean, the wording in `report.md` is consistently factual, and the audit's "A− for v0.1" feels accurate.

The biggest remaining gap is **not a measurement problem — it is an interpretation problem**. After reading findings across the 14 calibration runs, three things stand out:

1. **The findings layer is producing very similar lists for very different tracks.** Across an AI-generated Suno track (`aster`), a professional viral reference (`bunnyparty`), the author's most-worked-on human mix (`DC_kMM_Censored`), an intentionally distorted aesthetic piece (`rept`), and the oldest rough mix (`sufjanm`), I see the same five or six findings repeating: true peak above 0 dBTP, near-clipping, correlation min below 0, correlation dips below 0.3, side/mid above −6 dB, integrated loudness above −10 LUFS, centroid "elevated/reduced relative to this track's median." The findings layer is, in effect, detecting *modern stereo music with a contemporary loudness target* — which is a description of the dataset, not a fingerprint of any individual track.

2. **The "relative to this track's median" findings fire by construction.** If centroid moves at all, you can always pick a heuristic window where it is "elevated" and another where it is "reduced." On `aster` *both* fire. On `DC_kMM` *both* fire. This is not informative — it is geometry. These belong in the *plot caption*, not in the findings list.

3. **Several `why_it_matters` strings are tautologies.** The cleanest example, from `DC_kMM_Censored`: *"A higher side-to-mid ratio means side-channel RMS is closer to mid-channel RMS in the measured frames."* That's a definition, not a reason it matters. Same with the centroid "why it matters" line. These do real damage to user trust because they read as faux-substance.

The path forward, in priority order:

- **Cut the relative-shape findings entirely** (centroid elevated/reduced, band elevated/reduced, onset elevated), or demote them from `findings.json` to a single "spectral/dynamic activity map" caption beside the relevant plot.
- **Rewrite all `why_it_matters` strings** to describe a *real-world consequence* the user can hear or act on. If you cannot write that sentence honestly, the finding should not exist.
- **Reframe several thresholds as context, not flags.** Integrated LUFS > −10 is a *streaming-target relationship*, not an observation. PLR < 8 dB is a *genre/aesthetic relationship*, not a warning.
- **Introduce a calibration-folder view** that shows ranges and distributions, never rankings — and use it to teach users that "above 0 dBTP" or "side/mid > −6 dB" is normal across their catalog before any single-track finding fires for it.
- **In the HTML, lead with the plots and pair each finding to a specific plot** so the user is always being pointed at evidence rather than at a verdict-shaped card.

The rest of this document walks through the five requested deliverables.

---

## 1. Metric explanation framework

Format for every metric: plain-English → higher/lower implications → what it does NOT mean → in-song interpretation → catalog interpretation → suggested listening checks.

### 1.1 Integrated LUFS

- **Plain English:** A perceptual loudness number weighted to roughly match how loud humans hear the whole track, averaged over its full duration. Streaming services use a sibling of this measurement to normalize playback.
- **Higher / lower:** Higher (closer to 0) = louder average perceived level. Lower (more negative) = quieter average perceived level.
- **Does NOT mean:** Better/worse production, more/less compression by itself, or "ready for release." Two tracks at the same LUFS can sound completely different.
- **Within one song:** A single number for the whole file; pair with PLR and RMS to understand whether the loudness is sustained or peaky.
- **Across a folder:** Spread of LUFS shows aesthetic range, not quality range. A catalog with LUFS from −18 to −6 is a catalog with varied targets, not an inconsistent catalog.
- **Listening checks:** Compare loudness in a level-matched A/B against a track you know well at the same LUFS. Ask whether the loudness *feels* paid for by the arrangement.

### 1.2 True peak (dBTP)

- **Plain English:** An estimate of the highest peak a downstream D/A converter, codec, or limiter would *reconstruct* between samples — typically a little higher than the sample peak.
- **Higher / lower:** Above 0 dBTP means downstream playback chains can produce inter-sample peaks that exceed full scale. Below 0 leaves reconstruction headroom.
- **Does NOT mean:** Audible distortion is happening *in this file*. It means a player or encoder *may* clip on playback.
- **Within one song:** Pair with sample peak; a true peak well above sample peak indicates inter-sample energy worth knowing about before encoding to MP3/AAC.
- **Across a folder:** Useful drift signal — true-peak ceiling across an album tells you about delivery practice over time.
- **Listening checks:** Render a lossy encode at your delivery target and re-measure true peak in a meter you trust; A/B against the WAV.

### 1.3 Sample peak (dBFS)

- **Plain English:** The single largest absolute sample value in the file, expressed in dB relative to digital full scale.
- **Higher / lower:** At or above 0 dBFS = at least one sample at or beyond full-scale digital. Negative = headroom remaining.
- **Does NOT mean:** Anything about loudness, density, or perceived punch.
- **Within one song:** Mainly useful to know how close you are to integer-PCM ceilings before considering true peak.
- **Across a folder:** A folder where sample peak clusters at −0.1 to −0.3 dBFS suggests a normalization or limiter pass; a folder with more variance suggests a less-uniform delivery chain.
- **Listening checks:** None directly — pair with the sample histogram plot, which shows whether peaks cluster at the ceiling.

### 1.4 RMS (dBFS)

- **Plain English:** Average signal energy over the file (or over a frame), in dB relative to full scale. A rough "how much signal is moving" number.
- **Higher / lower:** Higher = more sustained energy, often associated with denser arrangements or heavier limiting. Lower = quieter or more dynamic.
- **Does NOT mean:** Loudness as a listener experiences it (LUFS is closer). Does not mean "well mixed" or "compressed."
- **Within one song:** The RMS *timeline* matters more than the single number — it shows where energy concentrates.
- **Across a folder:** RMS spread paired with PLR spread tells you about dynamics practice across the catalog.
- **Listening checks:** Skim the RMS timeline; mark the loudest and quietest passages and listen to the arrangement choices that produced them.

### 1.5 PLR (Peak-to-Loudness Ratio)

- **Plain English:** True peak minus integrated LUFS. A single number for "headroom left over the average loudness."
- **Higher / lower:** Higher PLR = more transient headroom relative to average loudness (often more dynamic feel). Lower PLR = less headroom (often denser, more limited, or distorted).
- **Does NOT mean:** A direct mastering quality score. Genre conventions differ wildly (pop limit-heavy masters often sit at PLR 6–9 dB; orchestral or jazz can sit at 15+ dB *by design*).
- **Within one song:** Useful with RMS and LUFS. If PLR is unusually low for the genre you're targeting, look at the limiter or arrangement density.
- **Across a folder:** A catalog whose PLR drops over time often reflects evolving loudness practice, not a quality trajectory.
- **Listening checks:** Compare against a same-genre reference you trust; ask whether transients sound intentional or squashed.

### 1.6 Clipped / near-clipping samples

- **Plain English:** Counts of samples at (or just below) the digital ceiling.
- **Higher / lower:** Any non-zero count of *clipped* samples means at least one sample hit full scale. Near-clipping counts show how often the signal flirts with the ceiling.
- **Does NOT mean:** Audible distortion is necessarily present (a handful of clipped samples in a 4-minute track may be inaudible); does not mean intentional distortion is bad.
- **Within one song:** Look at *where* the clipping clusters using the time ranges; intentional distortion is often broad and aesthetic, accidental clipping is often a single transient.
- **Across a folder:** A folder with consistent zero clipping suggests a careful delivery chain; non-zero clusters point to specific tracks worth inspecting.
- **Listening checks:** Solo the flagged passages; ask "did I want this to clip?"

### 1.7 Stereo correlation (L/R Pearson r)

- **Plain English:** How similar the left and right channels are, per frame. +1 = identical (mono-equivalent), 0 = uncorrelated, −1 = phase-inverted.
- **Higher / lower:** Closer to +1 = narrower, more mono-compatible. Closer to 0 or negative = wider; risks of mono summing loss or phase issues.
- **Does NOT mean:** A judgment about how "wide" or "good" the image is. Wide can be intentional; narrow can be intentional. Brief dips below 0 are *normal* on hi-hats, vocal throws, reverb tails, and stereo effects — they are not "phase problems."
- **Within one song:** Look at the *timeline* shape and the *duration* of low-correlation regions, not the minimum alone. Median is more diagnostic than min.
- **Across a folder:** Median correlation distribution shows the catalog's overall imaging tendency. Outliers (much narrower or much wider than the rest of the folder) deserve a listen, not a verdict.
- **Listening checks:** Switch to mono and check whether the elements you care about survive. If they don't, decide whether you care for *this* release.

### 1.8 Side/Mid ratio

- **Plain English:** RMS of the side channel (L−R) compared to the mid channel (L+R), in dB. How loud the "stereo difference" is relative to the "stereo center."
- **Higher / lower:** Higher (closer to 0 dB) = side energy approaches mid energy; the mix has substantial off-center content. Lower (more negative) = a more center-weighted mix.
- **Does NOT mean:** "Wide is good." Vocals, bass, and kick are typically center-weighted by design; a low side/mid is not a flaw.
- **Within one song:** Pair with stereo correlation timeline; together they describe the stereo field.
- **Across a folder:** A useful "stereo tendency" fingerprint across the catalog — modern pop often clusters in a recognizable side/mid range.
- **Listening checks:** A/B sections in mono. Note whether stereo-only elements (reverb, doubles, FX) are doing arrangement work or just decoration.

### 1.9 Spectral centroid

- **Plain English:** The "center of mass" of the spectrum in Hz — the frequency at which energy is balanced above and below.
- **Higher / lower:** Higher = energy is shifted toward higher frequencies in this frame. Lower = energy is shifted toward lower frequencies.
- **Does NOT mean:** Brightness as a listener perceives it. A track with bright cymbals but a huge sub can have a *low* centroid. Centroid is a statistic, not a subjective descriptor.
- **Within one song:** The centroid timeline shows arrangement changes (verses vs choruses, percussion entries, vocal presence). The single median is rarely interesting.
- **Across a folder:** Median centroid distribution is a "tonal balance" fingerprint of the catalog. Tracks with very different median centroids than the folder tend to differ in arrangement, not necessarily in mastering.
- **Listening checks:** Pull up the centroid plot beside the band-energy timeline. Ask whether each centroid swing has an obvious cause (new section, new element, dropout).

### 1.10 Spectral rolloff (85% / 95%)

- **Plain English:** The frequency below which X% of spectral energy sits. 95% rolloff is roughly "where does the track stop having serious energy."
- **Higher / lower:** Higher = energy extends further into the highs (often more high-frequency content). Lower = content rolls off earlier.
- **Does NOT mean:** "How high it sounds." A rolloff at 14 kHz with cymbals can sound less bright than a rolloff at 11 kHz with aggressive presence content.
- **Within one song:** Useful as a stable second view on top-end content. Less volatile than centroid.
- **Across a folder:** Rolloff distribution helps distinguish lo-fi/tape-style production (lower rolloff) from modern bright production (higher rolloff). Neither is better.
- **Listening checks:** Compare your 85% and 95% rolloff values against a reference track in the same aesthetic you trust.

### 1.11 Spectral bandwidth

- **Plain English:** The spread of energy around the centroid, in Hz. A "how wide is the spectrum around its center" number.
- **Higher / lower:** Higher = energy is spread across a wider frequency range. Lower = energy is concentrated in a narrower band.
- **Does NOT mean:** "Fuller" or "thinner" in a perceptual sense. A narrowband synth can feel huge; a wide-bandwidth track can feel thin if it lacks low end.
- **Within one song:** Most useful as a third view alongside centroid and rolloff for understanding spectral shape changes.
- **Across a folder:** Spread of bandwidth shows arrangement variety. A consistent bandwidth across many tracks suggests a consistent production palette.
- **Listening checks:** Look for frames with sudden bandwidth changes; these often correspond to instrumentation changes worth noting.

### 1.12 Average spectrum (Welch)

- **Plain English:** The long-term frequency profile of the whole track. "On average, where is the energy."
- **Higher / lower:** Bumps and dips show where the track is tonally concentrated. Strongest displayed bin is the *peak* of this average, normalized to 0 dB by definition.
- **Does NOT mean:** Calibrated dBFS. Every average-spectrum dB value is *relative to the strongest displayed bin in this file*. Two tracks' average-spectrum plots cannot be compared in absolute dB without re-normalization.
- **Within one song:** Reads as a tonal fingerprint. Look for unusual peaks (mains hum, resonances) and unusual gaps.
- **Across a folder:** Small-multiples view (one mini average-spectrum per track) is genuinely useful for catalog consistency. *Do not overlay raw curves* — they are relative-normalized per track.
- **Listening checks:** Use the strongest-bin and band-summary numbers to predict what you'll hear, then verify.

### 1.13 Band energy

- **Plain English:** The same average spectrum, summarized into seven named bands (sub, bass, low_mid, mid, presence, high, air).
- **Higher / lower:** Higher relative dB in a band = more energy concentrated there *relative to the strongest band in this track*.
- **Does NOT mean:** That the band is "loud" in absolute terms, or that the track has "too much/not enough" of that band. All values are relative to this track's peak band.
- **Within one song:** Identify the strongest band; pair with arrangement knowledge (sub-heavy 808 track vs. mid-heavy guitar track).
- **Across a folder:** *This is one of the most useful catalog views.* Plot each track's band energies as a small radar or stacked bar — patterns and outliers become visible without ranking.
- **Listening checks:** When a band is the strongest, ask which instrument is responsible.

### 1.14 Onset density

This is the metric the prompt specifically flagged as confusing. It deserves a longer treatment.

- **Plain English:** A smoothed timeline of *onset-detection strength* — how much percussive/transient activity the algorithm sees per moment. "How busy does the attack envelope look right now."
- **Important naming caveat:** Despite the name, this is **not** events-per-second. It is the time-smoothed output of `librosa.onset.onset_strength` in librosa's own arbitrary onset-strength units, with a boxcar smoothing window applied. The audit correctly flagged this naming as a stretch.
- **Higher / lower (within a track):** Higher in a region = more attack/transient activity than other moments in the same track. Lower = sparser texture.
- **Does NOT mean:**
    - "Punch." Punch is about attack envelope shape and headroom around the transient, not the count of transients.
    - "Tightness" or "groove." Onset density does not measure timing accuracy.
    - "Mix quality." A dense onset texture can be a wall of mud or a clean drum break.
    - "How many drum hits per second." It is a continuous strength curve, not a discrete count.
- **Within one song:** A useful *activity map*. Read it as "where does this track get busy and where does it breathe." Pair with the RMS and band-energy timelines to see whether busyness lines up with energy.
- **Across a folder — CRITICAL NUANCE:** **One track's onset-density numbers are not comparable to another track's onset-density numbers.** The values depend on FFT settings, signal level, frequency content, and librosa's internal normalization. A pad-heavy ambient piece with a single loud cymbal swell can have a peak onset value that looks numerically similar to a busy drum break in another track. The shape of the curve is meaningful within a song; the absolute scale across songs is not.
    - What *is* comparable across tracks: *patterns* (does this track have peaky onset activity or sustained?), and *median* as a very rough catalog signal — but treat it as "more / less attack-driven on average," never as "more / less punchy."
- **Listening checks:**
    - Pick the strongest onset-density region and listen to it; verify whether it lines up with a perceived activity peak.
    - Pick a quiet region in the timeline and listen for whether you actually hear a sparser texture.
    - If you want to compare two tracks' onset textures, listen to them — don't compare the numbers.

**Recommended language in the report for onset density (drop-in copy):**

> Onset density is an attack/activity map for *this track only*. Higher values mark moments with more transient activity than this track's median; lower values mark sparser moments. It is not a measure of punch, mix quality, or "drum hits per second," and the numeric scale is not comparable across different tracks.

### 1.15 Relative dB / track-normalized plots

This is the deepest interpretive trap in the report and deserves explicit framing.

- **Plain English:** Several plots and summary fields use "the strongest bin in this analysis = 0 dB" as their reference. They show *shape within this track*, not calibrated dB levels.
- **Does NOT mean:** dBFS. You cannot read "−12 dB relative" as "−12 dBFS." You cannot compare "−12 dB relative" in track A to "−12 dB relative" in track B.
- **Within one song:** Read these plots as *contour*. Where is the spectrum concentrated? Where does it dip? Where do bands cross?
- **Across a folder:** Only catalog summaries that re-normalize on a *common* reference can be compared across tracks. The current per-track relative dB values cannot be overlaid.
- **Listening checks:** Use the contour to predict what you'll hear, then listen. If the contour predicts a low-mid concentration and you hear an airy track instead, something is worth investigating.

**Recommended one-sentence banner** (place this above every relative-dB plot and section):

> Values in this plot are **relative to the strongest content in this track** (peak = 0 dB). They describe shape within this song and are not comparable to other tracks in dBFS.

---

## 2. Findings refinement

This is, by my read, the highest-leverage area in the project right now. The analysis is honest; the findings layer is currently over-interpreting it.

### 2.1 Concrete patterns from the calibration set

Going across all 12 main calibration tracks, the findings titles cluster into a small set:

| Finding | Tracks where it fires | Reading |
|---|---|---|
| True peak above 0 dBTP | 7/12 | High-value when it fires; user can act. |
| Near-full-scale samples | 6/12 | High-value when count is high; noisy when count is 1–5. |
| Sample clipping detected | 1/12 (sufjanm) | High-value, rare, actionable. |
| Min L/R correlation below 0 | 9/12 | Mostly noise. Brief dips are normal. |
| Correlation below 0.3 in some regions | 9/12 | Mostly noise. Same reason. |
| Median correlation below 0.5 | 3/12 | Moderate value — describes a wide track. |
| Median side/mid above −6 dB | 5/12 | Descriptive, not a finding. Move to details. |
| Integrated LUFS above −10 | 6/12 | Streaming-target context, not a finding. |
| PLR below 8 dB | 2/12 (rept, others) | Genre-dependent. Demote. |
| Centroid elevated relative to track median | 6/12 | Tautological. Demote or remove. |
| Centroid reduced relative to track median | 4/12 (often co-firing with elevated) | Same. |
| Centroid changes sharply | 3/12 | Same. |
| Multiple band-energy changes | 3/12 | Same. |
| Onset density elevated | 5/12 | Same. |
| Strongest band is X | varies | Should be in metric cards, not findings. |

The 7 tracks where *both* "centroid elevated" and "centroid reduced" fire are the clearest signal: any non-stationary signal produces both, because the heuristic is relative to its own median.

### 2.2 What's high-value (keep as findings)

These describe a real downstream consequence the user can act on:

- **Sample clipping detected** (always; rare; clear next step).
- **True peak above 0 dBTP** (clear delivery/encoding implication).
- **Near-clipping samples** when count is substantial *and* clusters in time (i.e. has at least one non-trivial time range).
- **Median correlation below ~0.4** combined with **sustained low-correlation duration** (i.e. not a 50 ms hi-hat dip — a real mono-compatibility story).
- **PLR below 8 dB** *with a "common in this style; check intended delivery" frame*, not as a warning.
- **Integrated LUFS far from common targets** *as a contextual note*, with the target shown (Spotify −14, YouTube −14, Apple −16, Tidal −14, CD/Bandcamp/club: no target).

### 2.3 What's noisy or low-signal (demote or remove)

- **All "X is elevated/reduced relative to this track's median" findings.** They fire mechanically on any track with motion. Move the underlying observation to a plot caption: *"Centroid varies between 1,840 Hz and 8,500 Hz over the track."* That sentence is true, useful, and has no implicit verdict.
- **"Minimum L/R correlation is below 0."** A 200 ms hi-hat dip below 0 is musically normal and should not be a top-eight finding. Replace with a duration-weighted measure (e.g., total duration below 0 as a percentage of file length) and surface only when sustained.
- **"Correlation below 0.3 in some regions."** Same problem, lower threshold.
- **"Median side/mid above −6 dB."** This is descriptive of stereo width. Move to stereo details. There is no consequence the user can hear or act on from this alone.
- **"Strongest band is X."** This is metadata for the metric card, not a finding.
- **"Multiple band-energy changes detected."** Means: the track has dynamics. Caption material.
- **"Strongest onset-density frame at T."** A single time stamp without context. Move to the onset plot caption.

### 2.4 What should be grouped

- All band-elevated/reduced observations should collapse into **one** "Spectral activity notes" entry that summarizes how many bands moved and links to the plot. The audit's complaint of 7 near-duplicate band findings is the most visible expression of this.
- All centroid/rolloff/bandwidth motion should collapse into **one** "Spectral shape motion" entry, or vanish into the plot caption.
- All correlation dip observations should collapse into **one** "Stereo width motion" entry with duration-weighted statistics.

### 2.5 What should move to technical details (out of findings)

- Side/mid ratio descriptive observations.
- Strongest band identification.
- Onset-density peak time.
- Centroid median / rolloff median / bandwidth median ranges.

### 2.6 Thresholds that are hard to justify

These should either be exposed in `AnalysisConfig` *with documentation that explains the choice*, or replaced with descriptive language:

| Threshold | Issue | Recommendation |
|---|---|---|
| PLR < 8 dB → "warning" | Genre-dependent; aggressive on EDM/pop, strict on jazz/orchestral | Demote to "info" and reframe as "PLR is X dB. Common ranges by aesthetic: 6–9 dB (loudness-targeted), 10–14 dB (moderately dynamic), 15+ dB (high-dynamic-range)." |
| LUFS > −10 → "info" | Treats above-streaming-target as noteworthy; many catalogs sit there intentionally | Replace with a "delivery context" block that simply *shows* the streaming targets and the file's value. No flag. |
| Correlation median < 0.5 → "warning" | Many intentionally wide tracks live here | Demote to "info"; require sustained duration before firing |
| Correlation min < 0 → "warning" | A single 50 ms dip triggers this | Require, e.g., min duration of low-correlation region, or report as a *fraction of time below threshold* |
| Side/mid median > −6 dB → "info" | Descriptive, not consequential | Remove as a finding; surface in details |
| Centroid ± max(1000, 0.5×median) → "info" | Fires on any non-stationary track | Remove from findings; surface in plot caption |
| Band elevated +6 dB / reduced −12 dB (asymmetric) → "info" | Asymmetric thresholds need a documented rationale; fires often | Either justify the asymmetry in docs, or unify; in either case demote to a single grouped finding |
| Onset density: median + max(0.15, 0.5×median) → "info" | Mechanical on any moving signal | Remove from findings; surface in plot caption |

### 2.7 Recommended finding wording patterns

Banned in findings text: *good, bad, professional, amateur, AI, broken, fix, issue (except literally as a severity), problem, mistake, should, must, need to.*

Preferred phrasings:

| Don't write | Write instead |
|---|---|
| "Why it matters: A higher side-to-mid ratio means side-channel RMS is closer to mid-channel RMS." | (Remove — definitions are not reasons.) |
| "Spectral centroid is elevated relative to this track's median" | (Remove from findings; caption: "Centroid moves between 1,840 Hz and 8,500 Hz across the file.") |
| "Minimum L/R correlation is below 0" | "L/R correlation dips below 0 for a total of X.X s (Y.Y% of the file) across N regions." |
| "PLR below 8 dB" / warning | "PLR measured at 6.4 dB. Common ranges in this aesthetic: 6–9 dB (loudness-targeted), 10–14 dB (moderately dynamic), 15+ dB (highly dynamic). No interpretation implied." / info |
| "Near-full-scale samples detected" with count = 1 | (Suppress under N=10 unless they cluster; otherwise: "12 near-clip samples cluster in a 0.09 s region at 72.96 s. Worth inspecting." with confidence note.) |

Required fields for every finding (refine the schema slightly):

- `title` — neutral, factual.
- `evidence` — the literal measurement.
- `why_it_matters` — must describe a *real downstream consequence the user can act on*. If you cannot write this honestly, the finding does not belong in `findings.json`. Acceptable consequences include: encoding/playback behavior, mono-fold survival, headroom for limiting, perceived loudness vs target. Not acceptable: restating the definition of the metric.
- `suggested_checks` — at least one is a specific plot and time range to look at; at least one is a listening action.
- `time_ranges` — required when present in the data, with duration totals.
- `not` (optional, recommended) — one short clause stating what this observation *does not* mean. This is the single biggest disambiguation tool against verdict-misreading.

### 2.8 Example language for 8 common findings

**1. Sample clipping**

> **Sample clipping detected**
> Evidence: 14 samples at or above ±1.0 in 2 regions.
> What this measures: at least one sample reached the digital ceiling.
> What it does not mean: the clipping is necessarily audible, or that it was unintentional.
> Suggested checks: open the sample histogram (`05_sample_histogram.png`); solo the time ranges 14.230–14.234 s and 88.901–88.917 s; ask whether the distortion is wanted.

**2. True peak above 0 dBTP**

> **Approximate true peak above 0 dBTP**
> Evidence: estimated true peak at +0.59 dBTP (sample peak −0.02 dBFS).
> What this measures: downstream playback or codec reconstruction may produce inter-sample peaks above full scale.
> What it does not mean: this file is distorting now, or that the file is "loud."
> Suggested checks: render at your delivery format (MP3/AAC/Opus) and re-measure with a dedicated true-peak meter; A/B against the source.

**3. Near-clipping cluster**

> **Near-full-scale sample cluster**
> Evidence: 1,482 samples ≥ ±0.99 (0.028% of total), clustering in 4 regions totaling 0.31 s.
> What this measures: passages where the signal sits very close to the digital ceiling.
> What it does not mean: clipping. Many limited and loud-targeted masters live here on purpose.
> Suggested checks: inspect the sample histogram; solo the largest cluster and ask whether the limiter behavior is intentional.

**4. Sustained low stereo correlation**

> **L/R correlation sits below 0.3 for a sustained period**
> Evidence: 18.4 s total below r = 0.3 (31% of file) across 6 regions; median r = 0.36.
> What this measures: significant portions of the file have weakly related or differing L and R content.
> What it does not mean: the stereo image is "wrong" or "phasey." Intentionally wide arrangements, stereo reverbs, and decorrelated FX can produce this.
> Suggested checks: switch to mono in the loudest sustained low-correlation region (e.g., 0:32–0:47); decide whether the elements you care about survive the fold-down.

**5. PLR context (info, not warning)**

> **PLR context: 6.4 dB**
> Evidence: true peak +0.5 dBTP, integrated loudness −6.0 LUFS.
> Reference ranges by aesthetic: 6–9 dB (loudness-targeted pop / EDM / hip-hop masters), 10–14 dB (moderately dynamic), 15+ dB (high-dynamic-range mixing).
> What this does not mean: a low PLR is "over-compressed" by itself. It describes a relationship, not a quality.
> Suggested checks: compare PLR against a reference track in the same aesthetic.

**6. Loudness target context**

> **Loudness target context: −6.0 LUFS integrated**
> Common normalization targets: Spotify −14 LUFS, Apple Music −16 LUFS, YouTube −14 LUFS, Tidal −14 LUFS, Amazon −14 LUFS. Bandcamp, CD, club, and download stores: no normalization.
> What this measures: the file's perceptual average level.
> What it does not mean: the file is "too loud" or "not loud enough." Different platforms will adjust playback level differently.
> Suggested checks: decide which platform context matters most for this release; render a level-matched A/B against the platform's normalized version of a reference.

**7. Spectral activity (grouped, info)**

> **Spectral activity notes**
> Centroid moves between 570 Hz and 8,500 Hz (median 2,870 Hz). 95% rolloff median 10.3 kHz. Bandwidth median 3.3 kHz.
> Per-band motion: sub varies ±32 dB relative; bass varies ±19 dB; low_mid varies ±20 dB; mid varies ±10 dB; presence/high/air mostly stable.
> What this measures: how much spectral shape changes over time.
> What it does not mean: motion is good or bad; many genres have heavy motion, many have little.
> Suggested checks: open `08_spectral_shape.png` and `09_band_energy_timeline.png` side by side with `02_rms_timeline.png` and identify what arrangement event drives each large shift.

**8. Onset-density activity map**

> **Onset activity map**
> Onset-strength density ranges 0.12 to 2.32 over the track (median 1.10). 7 regions above the track-internal "high activity" threshold; strongest at 77.5 s.
> What this measures: where in this track the attack envelope is busiest, relative to the track's own median.
> What it does not mean: punch, groove tightness, drum hits per second, or any comparison to another track. This metric is not cross-comparable between songs.
> Suggested checks: open `10_onset_density.png`; listen to the strongest region (76.0–79.0 s); listen to one of the quietest regions and confirm the texture difference.

---

## 3. Calibration-folder concept

The catalog/album view is one of the most exciting things AudioAtlas could build, *and* the easiest place to accidentally invent a scoring system. Below is a design that I think stays inside the "song microscope" framing.

### 3.1 Guiding principle

Calibration view answers **"how does the body of work spread on each axis?"** It never answers **"which track is best?"** No sort-by-best, no top-N, no badges, no rankings.

### 3.2 What the folder summary contains

For a folder of N tracks, generate a single `catalog_summary.json` (and matching `catalog.html`) with:

**A. Folder distribution per metric** (not a ranking — a distribution):
- For each scalar metric (LUFS, PLR, true peak, sample peak, RMS, median correlation, side/mid median, centroid median, rolloff 95%, etc.), the folder shows min, median, max, and a histogram or beeswarm.
- Each track is a dot, labeled, on each distribution.
- No axis is labeled "better" or "worse."

**B. Per-track fingerprints** (small multiples):
- For each track, a small "fingerprint card" with: filename, duration, LUFS, PLR, median correlation, strongest band, centroid median.
- Optional: a small radar chart with normalized band energies (so you can eyeball spectral shape similarity across the catalog at a glance).
- A small thumbnail of the band-energy timeline.

**C. Outlier notes (neutral, never ranked):**
- "This track sits further from the folder median on integrated LUFS than other tracks (−6.0 LUFS vs folder median −12.4 LUFS)."
- "This track has the widest stereo image in the folder by median correlation (0.36 vs folder median 0.78)."
- Note phrasing pattern: *"sits further from the folder median on X"* — never *"highest/lowest/best/worst."*

**D. Consistency view (if user labels the folder as an album):**
- LUFS spread across the album (range).
- True-peak spread.
- Strongest-band consistency (are all tracks low-mid dominant? Or mixed?).
- Side/mid spread.
- This view describes *consistency*, never says consistency is good or bad.

**E. Time drift (if files have datestamps from metadata or filename pattern):**
- Plot of LUFS over time, PLR over time, median centroid over time.
- Label-only narrative: *"Average LUFS rises 3.8 dB from oldest to newest file."* No verdict.

### 3.3 Suggested copy for the catalog header

> **Catalog view**
> This view shows how 12 tracks in this folder distribute on each measurement. It is not a ranking. There is no "best" axis. Use the dot positions to find outliers worth listening to and to understand the typical shape of your own work.

### 3.4 What the catalog view must NOT have

- A score per track.
- "Top tracks by X."
- Badges like "loudest," "widest," "brightest."
- Color-coding that implies green=good / red=bad. Use *neutral* coding (e.g., a single accent color for all dots; only the "your-track-here" highlight is a different shade).
- Any "compared to industry" overlay. Compare only against the user's own folder.
- AI/non-AI labels even if the tool could (it can't, and shouldn't claim to).

### 3.5 The "this track vs your folder" mini-block

This is the most useful single output the catalog view can provide. On each individual report, append a small block (only when a catalog context is provided):

> **Relative to your folder of 12 tracks**
> Integrated LUFS: −6.0 (folder range −18.2 to −6.0, median −12.4) — sits at folder top.
> PLR: 6.4 dB (folder range 5.1 to 14.8, median 9.1) — sits at folder bottom.
> Median stereo correlation: 0.66 (folder range 0.36 to 0.96, median 0.78) — within folder middle.
> Strongest band: low_mid (folder distribution: low_mid 6, bass 4, mid 2).

Note the language: *"sits at folder top," "within folder middle," "folder distribution."* Never *"highest," "loudest," "outlier."*

### 3.6 Calibration view as a teaching surface

A subtle but important use: the catalog view *teaches the user that the things the single-track findings flag are normal*. If a user sees their own catalog and 8 of 12 tracks have a "true peak above 0 dBTP" finding, they correctly conclude that this is descriptive of their delivery practice, not a defect. The catalog view is where the tool earns the user's trust to interpret single-track findings calmly.

---

## 4. HTML report UX

The mockup is in good shape — embedded CSS, vertical findings list, top nav, "how to read" callout, neutral notes areas. The recommendations below are refinements on top of an already-solid base.

### 4.1 Section order recommendation

Current order: header → "how to read" → key metrics → findings → plots (compact 6 + wide 4) → technical details → human notes.

Proposed order:

1. Header (filename, duration, format).
2. **"How to read this report"** callout (keep as-is, expand wording — see §5.3).
3. **Delivery & headroom** block (a focused subset of metrics: integrated LUFS, true peak, sample peak, clipped, near-clipping, PLR — the things with the clearest action implications).
4. **Findings** (vertical, capped, grouped — see §4.4).
5. **Plots** (paired with the relevant findings — see §4.3).
6. **Spectral & stereo overview** (the descriptive metrics: centroid, rolloff, bandwidth, correlation median, side/mid median).
7. **Technical details** (collapsibles).
8. **Catalog context** block (only if a catalog summary is present).
9. **Human notes**.

Rationale: putting *delivery & headroom* first puts the actionable measurements first, before any descriptive material. Findings then get to refer to specific plots that the user will scroll into next. Spectral/stereo overview is descriptive, so it can wait. Catalog context belongs near the bottom — it answers questions the user has after seeing the single-track view.

### 4.2 Key metric cards: refinement

The current 9 cards are fine, but they should communicate severity differently. Right now `metric-warning` is the only treatment used and it appears below the value. Suggestions:

- Use a small neutral status indicator under each card: *within typical range*, *check delivery format*, *worth a listen*. Avoid color-coding to red/green.
- Add a one-line "what this is" tooltip on hover for every metric card. Anchor the tooltip text in §1's plain-English definitions.
- Group cards into two rows: top row = delivery (LUFS, true peak, sample peak, PLR, clipped, near-clipping); bottom row = description (RMS, correlation median, side/mid median). This visually communicates that the top row has action implications and the bottom row is descriptive.
- Remove the LUFS, sample peak, and "0 clipped samples" cards if their value is mundane on a given run; show only what is interesting. (Or: gray them out instead of removing — the goal is to keep them findable without being a wall of zeroes.)

### 4.3 Pair every finding with a plot

Currently the findings list and plots list are independent sections. This is the single most valuable change to make in the HTML:

- Each finding card should include a small thumbnail or "see plot N at T:Tᴿ" link that scrolls to and highlights the relevant plot/time-range.
- The plots section should reciprocally annotate which findings reference each plot.
- Consider an *inline* layout where each finding has the relevant plot embedded directly under it, full-width, at the time range in question, instead of (or in addition to) the gallery layout. This makes the finding feel like a footnote on the plot rather than a verdict on the file.

### 4.4 Finding cards: refinement

Current card has: severity badge, category, title, evidence, why-it-matters, suggested checks, time ranges. Suggested additions:

- A new explicit `"This is not a..."` line directly under "Why it matters." Mirrors §2.7's recommendation. Calms the verdict-reading reflex.
- Inline the time-range list as a horizontal strip with the smallest waveform/RMS thumbnail (or, in the v0.x reality, just timestamps) so the user can click to the plot.
- A small "confidence" pill aligned with the severity badge. The schema already supports it; surface it.
- For grouped findings (e.g. "Spectral activity notes"), allow the card to expand a small inline table of the underlying observations without opening a separate page.

### 4.5 Plot order recommendation

Current pipeline order: 01 waveform+RMS, 02 RMS timeline, 03 log spectrogram, 04 average spectrum, 05 histogram, 06 stereo correlation, 07 mid/side energy, 08 spectral shape, 09 band-energy timeline, 10 onset density.

For the report, recommend:

1. **02 RMS timeline** (dynamics over time — the most readable starting point).
2. **01 Waveform + RMS envelope** (zoom-in counterpart).
3. **05 Sample histogram** (headroom story; pairs with the level metric cards).
4. **06 Stereo correlation** + **07 Mid/side energy** (stereo block).
5. **03 Log spectrogram** (full-width — the densest map; rewards careful inspection).
6. **04 Average spectrum** + **09 Band energy timeline** (frequency content overview).
7. **08 Spectral shape** (centroid/rolloff/bandwidth — descriptive).
8. **10 Onset density** (activity map — descriptive; goes last because it's the most easily misread).

The pipeline file numbering can stay; this is purely a *display* order in the HTML.

### 4.6 Plot captions

Every plot needs a one-sentence "what to look for" caption beneath it. Drop-in copy in §5.4. The relative-dB banner (§1.15) should appear above any plot that uses relative dB. The mockup currently does this only in the "how to read" callout at the top; it should repeat near the relevant plots because users scroll past callouts.

### 4.7 Glossary, tooltips, expandable definitions

Add a small footer-level "Glossary" section (or a `<details>` block in the header) with the §1.1–§1.14 plain-English definitions, no more than two sentences each. Link metric names in cards and findings to these definitions via `<a href="#glossary-lufs">`.

### 4.8 How to avoid overwhelming users

- Default report opens with *delivery & headroom + 3–4 findings + 4 plots visible above the fold*. Everything else is below or in `<details>`.
- Provide a "compact" / "expanded" toggle at the top. Compact = the minimum the user needs. Expanded = the full current report.
- Apply a hard cap of **5 findings shown by default**, with a "Show N more observations" disclosure. The current cap of 8 is too dense given the redundancy patterns in §2.1.
- Use whitespace generously between findings; current vertical card list is good for this.
- Never put more than one severity color visible at a time. If a "warning" finding is in the visible set, all "info" findings below it should be deemphasized typographically.

### 4.9 Making the report useful without being a judgment engine

The core philosophical move: **shift the language from observations *about* the track to observations *for* the listener**.

- Replace "Findings (8 shown)" with **"Suggested listening prompts (5 shown)"** as the section title.
- Replace card titles that read as verdicts ("L/R correlation falls below 0.3 in some regions") with prompt phrasings ("Worth a mono fold-down check: 6 regions where L/R correlation drops below 0.3").
- Replace `severity` badges of "warning" / "info" with prompt categories: **"Check before delivery," "Worth a listen," "For reference."** These communicate priority without implying defect.

This single relabeling, with no DSP changes, would probably eliminate 80% of the verdict-misreading risk.

---

## 5. Deliverables

### 5.1 Concise executive summary

(See §0.) The headline: the measurements are honest, the findings layer is over-interpreting them, and the path forward is (a) cut tautological findings, (b) rewrite `why_it_matters` strings to describe consequences, (c) add a catalog view that teaches users which findings are common-mode across their work, and (d) re-label findings as "listening prompts" rather than warnings.

### 5.2 Recommended report structure

(See §4.1.) Header → How to read → Delivery & headroom → Listening prompts → Plots paired with prompts → Spectral & stereo overview → Technical details → Catalog context (if available) → Human notes.

### 5.3 Metric glossary copy (drop-in)

Use the plain-English first sentence from each of §1.1 through §1.15 as the glossary body. Suggested header copy for the glossary section:

> **Glossary**
> Short definitions of every measurement that appears in this report. Each definition includes what the number means, what it does *not* mean, and how to read it within one song versus across a folder of work.

Suggested "How to read this report" copy (replacement for the current callout):

> **How to read this report**
> AudioAtlas measures one audio file and shows you the measurements. It does not score or judge your mix. Start with **Delivery & headroom** — those are the numbers that affect how the file behaves when you ship it. Then read **Listening prompts** — these are pointers to specific moments in the audio worth your ears, not problems the tool found. Open the matching plot for each prompt before deciding whether the prompt is relevant to your creative goals.
>
> A few things to know:
> - Relative-dB plots use *the strongest content in this track* as 0 dB. They show shape within this song; they are not calibrated dBFS and not comparable between tracks.
> - Onset-density values are not comparable between tracks. They are an activity map for *this* track.
> - "Above 0 dBTP," "side/mid above −6 dB," and similar phrases describe relationships. They are not defects.

### 5.4 Plot captions (drop-in copy)

- **02 RMS timeline:** *"Average signal energy over time. Look for where the track gets quietest, loudest, and how transitions land."*
- **01 Waveform + RMS envelope:** *"The raw sample shape with the energy envelope overlaid. Useful for inspecting specific transients and headroom near the ceiling."*
- **05 Sample histogram:** *"How sample values are distributed. Mass piled at the edges = sustained loudness or limiting near full scale."*
- **06 Stereo correlation:** *"How similar L and R are, per frame. +1 = mono-equivalent, 0 = uncorrelated, negative = phase-different content. Brief dips are normal."*
- **07 Mid/side energy:** *"Center content vs side content. Higher side = more off-center energy. This is descriptive, not a width score."*
- **03 Log spectrogram:** *"How frequency content moves over time. Brighter = more energy. Relative within this track."*
- **04 Average spectrum:** *"Long-term frequency profile of the whole track. Relative to this track's loudest frequency."*
- **09 Band energy timeline:** *"How seven broad frequency bands move over time. Relative within this track; bands in different songs are not directly comparable."*
- **08 Spectral shape:** *"Centroid, rolloff, and bandwidth over time — three views of where the spectral 'center of mass' sits and how it moves."*
- **10 Onset density:** *"Activity map: where the attack envelope is busiest, relative to this track's own median. Not comparable across tracks. Not a measure of punch."*

### 5.5 Recommended finding wording patterns

(See §2.7.) Required structure per finding: `title (neutral)`, `evidence (literal measurement)`, `why_it_matters (real downstream consequence — if you can't write it honestly, the finding doesn't exist)`, `not (one-clause "this does not mean ___")`, `suggested_checks (≥1 plot+timestamp, ≥1 listening action)`, `time_ranges`, `confidence`.

### 5.6 Catalog-folder dashboard concept

(See §3.) Folder-distribution histograms per metric → per-track fingerprint cards → neutral outlier notes → consistency view (if labeled as album) → time drift (if dates present) → "this track vs your folder" block on each single-track report. No rankings, no badges, no top-N.

### 5.7 Example language for 8 common findings

(See §2.8 — eight worked examples covering: sample clipping, true peak >0 dBTP, near-clipping cluster, sustained low stereo correlation, PLR context, loudness target context, spectral activity notes, onset activity map.)

### 5.8 Prioritized "change next" list

In order of leverage. Each is small enough to be a single feature slice; none requires DSP changes.

**Tier 1 — language and finding-shape changes (do these first; highest leverage, lowest risk):**

1. **Rewrite every `why_it_matters` string** to state a real downstream consequence. Audit each finding type with the test "would a musician care about the answer to *why does this matter*?" If no, the finding gets demoted to a plot caption or removed.
2. **Remove the "X is elevated/reduced relative to this track's median" findings** for centroid, band energy, and onset density. Replace with one grouped "Spectral activity notes" finding plus plot-caption summaries.
3. **Add a `"not"` clause to the finding schema** and populate it for every finding. One sentence per finding stating what the observation does *not* mean.
4. **Relabel the section title from "Findings" to "Listening prompts."** Relabel severity values from `info/warning/issue` to `for_reference / worth_a_listen / check_before_delivery` (or equivalent). Pure wording change, big tone shift.
5. **Add the "relative dB" banner** above every relative-dB plot and every relative-dB section in `report.md`. The current banner is in one callout; it needs to repeat next to the plots themselves.

**Tier 2 — threshold and structural changes:**

6. **Make correlation findings duration-weighted.** A 50 ms hi-hat dip should not produce a "warning." Replace `min < 0` with `total duration below 0 > X% of file` or `single sustained region > Y seconds`.
7. **Demote LUFS > −10 from finding to a "delivery target context" block** that shows the file's LUFS alongside platform normalization targets. No verdict.
8. **Demote PLR < 8 dB from warning to info,** and reframe with genre/aesthetic reference ranges.
9. **Cap default visible findings at 5** with disclosure for the rest.
10. **Suppress near-clipping findings under 10 samples** unless they cluster in a non-trivial time range.

**Tier 3 — catalog and HTML report:**

11. **Build the catalog summary view** (folder distributions, fingerprint cards, "this track vs your folder" block).
12. **Move HTML report to "delivery & headroom first" structure** with plots paired to findings.
13. **Add tooltips/glossary cross-links** from every metric card and finding to the §1 definitions.
14. **Add a "compact / expanded" toggle** to the HTML report.

**Tier 4 — measurement honesty refinements:**

15. **Rename `onset_density` summary field** to something like `onset_strength_activity` to match what it actually measures (the audit flagged this; it's not a true per-second density). Bump schema_version.
16. **Add per-band absolute energy** alongside relative energy. This makes "elevated/reduced" findings (if any survive) more honest by showing the absolute scale.
17. **Expose `correlation_min_rms_dbfs`, `db_floor`, and the new duration thresholds** in CLI flags so power users can tune for quiet or hot material without code changes.

---

## Closing thought

The instinct behind AudioAtlas — *measure, don't judge* — is genuinely rare in audio tooling and is the project's biggest differentiator. The remaining work is mostly about making sure the *report* communicates that same humility as clearly as the DSP layer already does. The current findings layer is the one place where the tool's voice slips into "let me tell you what I found wrong" mode, mostly through phrasing rather than intent. Fixing the language and the relative-shape findings is, in my read, more important than any new measurement at this stage.

A creator opening their first AudioAtlas report should come away thinking *"this is a map I can read,"* not *"this is a list of things to fix."* The Tier 1 changes above are aimed squarely at making the second reading impossible.

— Claude

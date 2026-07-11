# AudioAtlas Compatibility Policy

AudioAtlas uses several version axes because package delivery, serialized data,
finding semantics, and output ownership do not always change together.

## Version axes

| Axis | Current value in `0.2.0a3` | Changes when |
|---|---:|---|
| Python package | `0.2.0a3` | any release is published |
| Summary schema | `0.2.0` | documented summary fields are removed, retyped, renamed without an alias, or change meaning |
| Findings schema | `0.2.0` | finding object structure changes incompatibly |
| Catalog schema | `0.2.0` | catalog object structure changes incompatibly |
| Finding ruleset | `0.2.0a2` | default rule eligibility, priority, or interpretive contract changes |
| Output manifest | `1` | ownership/publication manifest structure changes incompatibly |

A package release may therefore keep an earlier ruleset version when it changes
tooling, documentation, or delivery behavior without changing the rules. That
is deliberate, not version drift.

## Canonical names and temporary aliases

The canonical broad-band language is **relative mean band power per included
FFT bin**.

Canonical serialized names:

- `band_power_timeline`
- `band_mean_power`
- `mean_power_db`
- `highest_mean_power_band`
- `highest_mean_power_band_by_median`

Deprecated compatibility aliases:

- `band_energy_timeline`
- `band_energies`
- `energy_db`
- `strongest_band`
- `strongest_band_by_median`

Python compatibility names also remain available for
`BandEnergyTimelineResult`, `compute_band_energy_timeline`, and related adapter
entry points.

The historical graph key and filename `band_energy_timeline` /
`band_energy_timeline.png` remain stable during the `0.x` line. Their visible
display name and caption describe the actual mean-power measurement. Keeping the
file identity avoids breaking saved graph configurations and report links while
preventing the user-facing label from repeating the old implication.

## Alias lifecycle decision

1. All listed aliases remain available throughout the `0.2.x` alpha line.
2. New code and documentation must use canonical names.
3. Alias removal may occur no earlier than `0.3.0`.
4. Removal requires the relevant schema-version bump, changelog entry, migration
   table, tests, and a release note that names every removed field.
5. No alias may silently change meaning before removal.
6. AudioAtlas does not emit runtime deprecation warnings for serialized aliases
   during `0.2.x`; warnings would add noise to report generation without helping
   most end users. Documentation and code comments carry the deprecation state.
7. The graph key/filename has the longer `0.x` stability promise above and is
   not automatically removed with JSON aliases.

This policy resolves the temporary-alias question without forcing an avoidable
schema break during calibration.

## Consumer guidance

- Prefer canonical fields immediately.
- Record package, schema, and ruleset versions when archiving calibration or
  downstream analysis.
- Do not infer that matching package versions imply matching serialized schemas,
  or vice versa.
- Treat unknown additive fields as optional unless the schema guide says
  otherwise.
- Reject or migrate data when a required major/minor schema version is not
  supported; do not guess at renamed meanings.

## Change checklist

Any compatibility-affecting patch must update, in the same change:

- `src/audioatlas/release.py`;
- serializers and compatibility readers;
- `docs/SUMMARY_SCHEMA.md` and this policy;
- focused migration/round-trip tests;
- `docs/CHANGELOG.md`;
- package/release verification notes.

# AudioAtlas song-project schema

Song projects keep user-asserted revisions of one track in a local static
workspace. Project schema `0.1.0` has two deliberately different surfaces.

## Owner-side configuration

`audioatlas-project.yaml` is private operational state. AudioAtlas creates and
updates it atomically. It contains:

| Field | Meaning |
|---|---|
| `schema_version` | Song-project schema version. |
| `name` | User-supplied project label. |
| `project_id` | Random raw local identity token shared by revision reports. |
| `created_at` | UTC creation timestamp. |
| `graphs_profile` | Plot profile applied consistently to revisions and sections. |
| `theme` / `presentation` | Static report appearance defaults. |
| `sections` | Optional reusable manual name/start/end ranges. |
| `revisions` | Ordered local source paths and generated artifact references. |

The configuration can contain absolute source paths and the raw identity token.
It is not a share-safe artifact and is never linked from the generated HTML.

## Portable generated index

`project.json` contains:

- `schema_version`, `audioatlas_version`, and `project_kind`;
- the project name and graph profile;
- `project_id_sha256`, never the raw project token;
- ordered revision labels, portable source filenames, durations, report links,
  manual-section links, and guarded adjacent-diff links;
- an explicit non-ranking interpretation boundary.

`project.md` and `project.html` present the same revision order and links. They
do not contain source paths, audio, scores, preferred revisions, or inferred
song identity.

## Compatibility

Project schema `0.1.x` may gain additive fields. Removing, renaming, retyping,
or changing the meaning of an existing field requires a project-schema bump,
migration note, changelog entry, and focused configuration/index tests.

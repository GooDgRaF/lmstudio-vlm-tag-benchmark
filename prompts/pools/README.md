# Tag Pools

This directory contains tag pool files used by pool-based benchmark modes.

The runner uses these canonical files:

- `ru_plain.txt`
- `en_plain.txt`
- `ru_explained_ids.tsv`
- `en_explained_ids.tsv`

Additional pool drafts may live here, but configs should point to the canonical files unless a run intentionally tests another pool.

## Plain Pools

Files:

- `ru_plain.txt`
- `en_plain.txt`

Format:

```text
one tag per line
```

Parser rules:

- trim each line;
- skip empty lines;
- skip comment lines starting with `#`;
- keep original spelling and case.

Plain pool modes expect the model to return tags, one per line.

## Explained Pools

Files:

- `ru_explained_ids.tsv`
- `en_explained_ids.tsv`

Format:

```text
id<TAB>tag<TAB>explanation
```

Example:

```text
RU001	Common	Safe for all audiences.
EN001	Common	Safe for all audiences.
```

Prompt-ready text is generated at runtime:

```text
RU001	Common - Safe for all audiences.
EN001	Common - Safe for all audiences.
```

Explained pool modes expect IDs only, one per line:

```text
RU001
RU017
RU054
```

The runner validates IDs against the TSV file and maps accepted IDs back to canonical tag names.

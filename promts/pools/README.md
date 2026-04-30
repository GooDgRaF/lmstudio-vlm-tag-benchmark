# Tag pools

This folder contains the normalized tag pool files used by the benchmark.

Only four runner pool files are kept here:

- `ru_plain.txt`
- `en_plain.txt`
- `ru_explained_ids.tsv`
- `en_explained_ids.tsv`

## Plain pools

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

For plain-pool modes, the model returns tags (line format by default in current configs).

## Explained pools

Runner v1 uses ID-based explained pools:

- `ru_explained_ids.tsv`
- `en_explained_ids.tsv`

Format:

```text
id<TAB>tag<TAB>explanation
```

Example:

```text
RU001	Общий	Безопасно для всех.
EN001	General	Safe for all audiences.
```

Prompt-ready text is generated at runtime from TSV in this format:

```text
RU001	Общий - Безопасно для всех.
EN001	General - Safe for all audiences.
```

No separate prompt files or JSON copies are stored in `pools/`.

For explained-pool modes, the model should answer with IDs only, one per line:

```text
RU001
RU017
RU054
```

The runner validates IDs against TSV and maps accepted IDs back to canonical tag names.

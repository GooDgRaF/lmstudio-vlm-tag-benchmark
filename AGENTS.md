# AGENTS.md

Инструкция для coding agents, работающих с этим репозиторием. Цель — быстро войти в контекст и не тратить лишние вызовы на поиск уже описанной структуры.

## Быстрый маршрут ознакомления

Читайте в таком порядке:

1. `README.md` — короткий вход, команды, ссылки.
2. `PROJECT_GUIDE.md` — навигация по каталогам, конфигам, результатам и основному usercase.
3. `ARCHITECTURE.md` — контракт форматов и ограничений v1.
4. `pools/README.md` — если задача касается тегов или pool validation.
5. `specs/README.md` и текущий `specs/XX-*.md` — если задача связана с активной спецификацией. Завершенные спеки лежат в `specs/archive/`.

После чтения выполните:

```bash
git status --short --branch
python main.py dry-run --config config.smoke.yaml
python -m pytest -q
```

`config.smoke.yaml` — основной быстрый runtime-профиль: одна модель, одна картинка, все шесть режимов.

## Главный вертикальный слайс

Основная цепочка находится в `src/runner.py`:

```text
load config
load tag pools
discover images
create results/<run_id>/
check LM Studio
unload existing loaded instances
load model
run image smoke-test
run model requests for image x mode
save raw JSON
normalize response
append summary.csv row
unload model
build report.html
```

Если задача формулируется как «проверить, что проект работает», используйте:

```bash
python main.py run --config config.smoke.yaml
```

После запуска смотрите `results/<run_id>/report.html`, `diagnostics.html`, `summary.csv`, `errors.log`.

## Карта модулей

```text
main.py                 CLI commands
src/config.py           YAML -> dataclasses
src/validator.py        config validation + model response normalization
src/lmstudio_client.py  LM Studio API wrapper
src/runner.py           sequential benchmark runner
src/storage.py          run folders, request ids, summary CSV
src/report.py           static HTML report
src/prompts.py          prompts and response_format schema
src/tag_pools.py        pool file loading and ID mapping
src/image_loader.py     image discovery and image_id generation
src/diagnostics.py      nvidia-smi, context/token diagnostics
```

Start with `src/runner.py` for end-to-end behavior. Then follow imports to the specific subsystem.

## Конфиги и когда их использовать

- `config.smoke.yaml` — quick verification and development checks.
- `config.example.yaml` — full benchmark config with all active model variants.

Prefer smoke for agent work. Use full config only when the user explicitly asks for a real benchmark or model comparison.

Before running a full benchmark, call:

```bash
python main.py dry-run --config config.example.yaml --limit 1
```

Full `config.example.yaml` without `--limit` can run many model/image/mode requests.

## LM Studio notes

LM Studio endpoints are configured in YAML:

```yaml
lmstudio:
  api_base_url: "http://localhost:1234/api/v1"
  openai_base_url: "http://localhost:1234/v1"
```

The runner loads a model through `/api/v1/models/load` and sends chat requests to the returned `instance_id`. This keeps inference attached to the loaded instance.

The runner also calls best-effort unload cleanup:

- before each model load;
- after each model run when `runtime.unload_model_after_run: true`.

If the user reports multiple loaded LM Studio instances, inspect:

- `src/runner.py`;
- `src/lmstudio_client.py`;
- `results/<run_id>/models/<model_label>/load.json`;
- `results/<run_id>/errors.log`;
- `client.list_models()` output.

## Result files

For debugging a run, inspect in this order:

1. `results/<run_id>/report.html`
2. `results/<run_id>/diagnostics.html`
3. `results/<run_id>/diagnostics.json`
4. `results/<run_id>/summary.csv`
5. `results/<run_id>/errors.log`
6. `results/<run_id>/models/<model_label>/load.json`
7. `results/<run_id>/models/<model_label>/smoke_test.json`
8. `results/<run_id>/normalized/<request_id>.json`
9. `results/<run_id>/raw/<request_id>.json`

`pool_validation_failed` means the model returned values outside the configured pool. Treat it as benchmark signal unless the user is asking to change pool behavior.

## Test strategy

Default:

```bash
python -m pytest -q
```

Focused checks:

```bash
python -m pytest -q tests/test_runner.py
python -m pytest -q tests/test_lmstudio_client.py
python -m pytest -q tests/test_response_parsing.py
python -m pytest -q tests/test_report.py
```

Use `dry-run` after config/path changes:

```bash
python main.py dry-run --config config.smoke.yaml
```

Use real `run` only when runtime behavior or the usercase needs verification through LM Studio.

## Editing rules for this repo

- Keep v1 as a simple CLI benchmark.
- Prefer small, local changes matching existing modules.
- Do not add GUI, web-server, SQLite, async runner, plugin-system, judge-model, or non-LM-Studio backend unless the user asks.
- Do not delete or rename files in `ImgToTag/` unless the user explicitly asks; they are user data.
- Do not commit generated `results/*`; they are ignored except `results/.gitkeep`.
- Do not change pool semantics casually. Pool violations are diagnostic output, not automatically a code bug.
- Update docs when behavior, CLI commands, config keys, output shape, or project structure changes.

## Common tasks

### Change the number of smoke images

Edit:

```yaml
limits:
  limit_images: 1
```

in `config.smoke.yaml`.

### Add or remove a benchmark mode

Touchpoints:

- config `modes`;
- `src/prompts.py`;
- `src/validator.py`;
- tests for prompts and parsing;
- docs if the mode is user-facing.

### Add a summary column

Touchpoints:

- `src/storage.py` CSV header;
- `src/runner.py` append row payload;
- `src/report.py` if visible in HTML;
- `tests/test_summary_csv.py`;
- `tests/test_report.py` if relevant.

### Change report layout

Touchpoints:

- `src/report.py`;
- `tests/test_report.py`;
- smoke run for visual sanity.

### Change LM Studio payloads

Touchpoints:

- `src/lmstudio_client.py`;
- `tests/test_lmstudio_client.py`;
- real `python main.py list-models --config config.smoke.yaml` if LM Studio is running;
- smoke run if load/chat/unload behavior changed.

## Useful commands

```bash
rg --files
rg -n "run_benchmark|load_model|chat_completion|summary.csv|report.html" src tests
python main.py validate-config --config config.smoke.yaml
python main.py dry-run --config config.smoke.yaml
python -m pytest -q
```

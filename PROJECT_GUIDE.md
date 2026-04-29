# Project Guide

Этот документ — рабочая карта репозитория Local VLM Image Tagger Benchmark: где что лежит, какие команды использовать и куда смотреть при типичных задачах.

## Основной usercase

Главный вертикальный слайс проекта:

```text
изображение в ImgToTag/
  -> конфиг
  -> LM Studio model load
  -> REST smoke image request
  -> шесть режимов тегирования
  -> LM Studio REST Chat (/api/v1/chat)
  -> raw JSON
  -> normalized JSON
  -> summary.csv
  -> report.html
  -> model unload
```

Для быстрой проверки используйте:

```bash
python main.py run --config config.smoke.yaml
```

`config.smoke.yaml` содержит одну модель и `limit_images: 1`, поэтому он подходит для ежедневной проверки пайплайна.

Для полного прогона используйте:

```bash
python main.py run --config config.example.yaml
```

Полный прогон может быть долгим: он использует все модели из `config.example.yaml` и все изображения из `ImgToTag/`.

## Навигация по корню

```text
README.md             короткий вход и основные команды
PROJECT_GUIDE.md      подробная карта проекта
AGENTS.md             инструкция для coding agents
ARCHITECTURE.md       архитектурный контракт и форматы v1
main.py               CLI entrypoint
config.smoke.yaml     быстрый smoke-конфиг
config.example.yaml   полный пример конфигурации
requirements.txt      Python-зависимости
stats.json            численная сводка по моделям и пулам
ImgToTag/             входные изображения пользователя
models/               списки моделей LM Studio
pools/                нормализованные tag pools
results/              артефакты запусков
specs/                спецификации этапов реализации
src/                  код приложения
tests/                pytest-тесты
```

## CLI

Точка входа — `main.py`.

Команды:

```bash
python main.py validate-config --config config.smoke.yaml
python main.py dry-run --config config.smoke.yaml
python main.py list-models --config config.smoke.yaml
python main.py run --config config.smoke.yaml
python main.py run --config config.smoke.yaml --run-id smoke-001
python main.py run --config config.smoke.yaml --run-id smoke-001 --force-lock
python main.py collect --run results/<run_id>
python main.py report --run results/<run_id>
```

Когда использовать:

- `validate-config` — после изменения YAML-конфигов, путей, моделей, режимов, pools.
- `dry-run` — перед запуском benchmark, чтобы увидеть количество моделей, режимов и картинок.
- `list-models` — когда нужно проверить доступность LM Studio API и список моделей.
- `run` — основной запуск benchmark; при `report.generate_html: true` создает HTML-отчет автоматически.
- `run --run-id <id>` — продолжить/повторить конкретный run-каталог с манифестом запросов.
- `run --force-lock` — снять stale `run.lock` после аварийного завершения.
- `collect --run` — пересобрать `summary.csv` и `diagnostics.json` из request-артефактов.
- `report` — пересобрать HTML для уже существующей папки `results/<run_id>`.

## Конфиги

### `config.smoke.yaml`

Основной быстрый тестовый конфиг:

- одна модель: `qwen/qwen3-vl-4b@q4_k_m`;
- все шесть режимов тегирования;
- `limits.limit_images: 1`;
- HTML-отчет включен;
- resume включен;
- unload модели после запуска включен.

Используйте его для проверки изменений в коде и в вертикальном слайсе.

### `config.example.yaml`

Полный пример benchmark-конфига:

- 8 model variants;
- все шесть режимов;
- та же структура pools и diagnostics;
- `limit_images: null`, если CLI не передает `--limit`.

Используйте его для реального сравнения моделей. Для безопасной короткой проверки полного конфига добавляйте `--limit 1`.

### `config.rest-reasoning-smoke.yaml`

Малый e2e-профиль для проверки REST reasoning-сценария:

- 2 профиля одной модели (`reasoning: on/off`);
- 1 изображение;
- 2 режима;
- артефакты и HTML-отчеты как в обычном run.

## Входные изображения

Папка входа:

```text
ImgToTag/
```

Поддерживаемые расширения задаются в конфиге:

```yaml
input:
  extensions:
    - ".jpg"
    - ".jpeg"
    - ".png"
    - ".webp"
    - ".bmp"
```

Логика поиска находится в `src/image_loader.py`.

Важно:

- `recursive: false` означает только файлы верхнего уровня;
- сортировка стабильная, по относительному пути;
- `image_id` строится из имени файла и короткого hash относительного пути;
- CLI `--limit` имеет приоритет над `limits.limit_images`.

## Модели

Основные файлы:

```text
models/models.active.yaml
models/models.excluded.yaml
models/lmstudio-models.raw.json
```

`models.active.yaml` содержит model variants, используемые в полном конфиге. `models.excluded.yaml` хранит модели, которые не входят в benchmark, с причинами исключения. `lmstudio-models.raw.json` — исходный экспорт из LM Studio.

В runtime модель загружается через `src/lmstudio_client.py`, затем запросы отправляются в загруженный `instance_id` через REST Chat. Это удерживает benchmark на одном явно загруженном инстансе и снижает риск неявной второй загрузки в LM Studio.

## Tag pools

Runner использует четыре файла:

```text
pools/ru_plain.txt
pools/en_plain.txt
pools/ru_explained_ids.tsv
pools/en_explained_ids.tsv
```

Plain-pool формат:

```text
one tag per line
```

Explained-pool формат:

```text
id<TAB>tag<TAB>explanation
```

Подробнее: [pools/README.md](pools/README.md).

Код загрузки и валидации: `src/tag_pools.py`.

## Режимы тегирования

Список режимов задается в `modes` конфига:

```text
ru_free
ru_pool
ru_pool_explained
en_free
en_pool
en_pool_explained
```

Промпты строятся в `src/prompts.py`.

Ответы нормализуются в `src/validator.py`.

Правила:

- максимум тегов задается `limits.max_tags`;
- free/plain modes по умолчанию используют `line_tags` (один тег на строку);
- parser продолжает поддерживать `strict_json` для обратной совместимости и альтернативных конфигов;
- explained modes ожидают ID тегов;
- теги вне pool сохраняются в rejected-полях;
- `pool_validation_failed` в summary означает диагностированное нарушение pool-режима.

## Результаты

Каждый запуск создает:

```text
results/<run_id>/
  run_config.yaml
  models.json
  run_manifest.json
  run_state.json
  run_complete.json
  summary.csv
  report.html
  errors.log
  requests/
  raw/
  normalized/
  assets/thumbs/
  models/<model_label>/
```

Что смотреть:

- `report.html` — первая точка входа после запуска (answer matrix для сравнения моделей по image x mode);
- `report.html` также показывает компактный timing-summary и корректно печатается через браузерный print preview;
- `summary.csv` — таблица по всем запросам;
- `normalized/<request_id>.json` — детальная диагностика конкретного запроса;
- `normalized/<request_id>.json` хранит отдельно `final_content` и `reasoning_content`; теги парсятся только из `final_content`;
- `requests/<request_id>/` — каноничные request-артефакты (`request/status/raw/normalized/diagnostics`);
- `raw/<request_id>.json` — исходный ответ LM Studio;
- `models/<model_label>/load.json` — фактический load config и `instance_id`;
- `models/<model_label>/smoke_test.json` — результат image smoke-test;
- `errors.log` — cleanup, skip/resume, ошибки загрузки и выгрузки.

`results/*` игнорируются git-ом, кроме `results/.gitkeep`.

Источник истины: `requests/<request_id>/*` + `models/*` + `run_manifest.json`.  
`summary.csv`, `diagnostics.json`, `report.html`, `diagnostics.html` считаются производными и могут быть пересобраны.

Для повторных прогонов в тот же `run_id`:

- `result_mode: deterministic` переиспользует успешные запросы;
- `result_mode: overwrite` пересчитывает каноничные результаты;
- `result_mode: accumulate` добавляет новую попытку в `requests/<request_id>/attempts/NNN/` и сохраняет историю.

## Код

```text
src/config.py           dataclass-конфиг и YAML loader
src/validator.py        semantic config validation и response normalization
src/lmstudio_client.py  LM Studio API client
src/runner.py           основной sequential benchmark loop
src/storage.py          структура results и CSV writer
src/report.py           статический HTML report
src/prompts.py          prompt builder и response_format schema
src/tag_pools.py        plain/explained pool loaders
src/image_loader.py     обнаружение изображений
src/diagnostics.py      GPU/context diagnostics
```

## Тесты

Запуск:

```bash
python -m pytest -q
```

Основные тестовые зоны:

- `tests/test_config.py`, `tests/test_validator.py` — конфиг и валидация;
- `tests/test_lmstudio_client.py` — HTTP-клиент LM Studio через monkeypatch;
- `tests/test_runner.py` — вертикальный слайс runner-а;
- `tests/test_report.py` — HTML report;
- `tests/test_response_parsing.py` — JSON/line/ID parsing;
- `tests/test_tag_pools.py` — загрузка pools.

## Как расширять

## HTML outputs

- `report.html` is the answer matrix for manual model comparison.
- `diagnostics.html` is a detailed runtime/service diagnostics page.
- `python main.py report --run results/<run_id>` rebuilds both HTML reports when diagnostics data is present.

### Добавить модель

1. Добавьте модель в `models/models.active.yaml`.
2. Добавьте соответствующий блок в нужный конфиг.
3. Проверьте `max_context_length`, `params`, `quant`, `quant_bits`.
4. Запустите:

```bash
python main.py validate-config --config config.example.yaml
python main.py dry-run --config config.example.yaml --limit 1
```

### Добавить тег в pool

1. Измените один из файлов `pools/*.txt` или `pools/*_ids.tsv`.
2. Сохраните формат файла.
3. Запустите:

```bash
python main.py validate-config --config config.smoke.yaml
python -m pytest -q tests/test_tag_pools.py
```

### Изменить prompt или parser

1. Меняйте `src/prompts.py` или `src/validator.py`.
2. Проверьте `tests/test_prompts.py` и `tests/test_response_parsing.py`.
3. Для изменения смысла промпта обновите `PROMPT_VERSION`.

### Изменить HTML-отчет

1. Меняйте `src/report.py`.
2. Проверьте:

```bash
python -m pytest -q tests/test_report.py
python main.py run --config config.smoke.yaml
```

## Что держать простым

v1 — локальный CLI benchmark. Для этой версии не нужны GUI, web-server, SQLite, async runner, judge-модель, plugin-system и backend-ы кроме LM Studio.


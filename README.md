# Local VLM Image Tagger Benchmark

CLI-проект для сравнения локальных vision-language моделей в LM Studio на задаче автоматического тегирования изображений.

Основной сценарий:

```text
ImgToTag/ -> python main.py init-config -> python main.py run --config config.yaml -> results/<run_id>/report.html
```

Проект ориентирован на воспроизводимый локальный benchmark: он загружает выбранные модели, отправляет изображения с промптами через LM Studio REST Chat (`/api/v1/chat`), сохраняет сырые ответы, нормализованные результаты, CSV-сводку и статический HTML-отчет.

## Быстрый старт

1. Запустите LM Studio server на `localhost:1234`.
2. Положите изображения в папку `ImgToTag/`.
3. Сгенерируйте пользовательский конфиг:

```bash
python main.py init-config
```

4. Проверьте план:

```bash
python main.py dry-run --config config.yaml
```

5. Запустите benchmark:

```bash
python main.py run --config config.yaml
```

`config.yaml` — основной user-facing конфиг: модели и режимы уже перечислены под `models:` и `modes:`. Достаточно комментировать/раскомментировать элементы списка без copy-paste.

После завершения откройте:

```text
results/<run_id>/report.html
```

## Основные команды

```bash
python main.py init-config
python main.py refresh-models
python main.py list-models
python main.py validate-config --config config.yaml
python main.py dry-run --config config.yaml
python main.py run --config config.yaml
python main.py run --config config.yaml --run-id smoke-001
python main.py run --config config.yaml --run-id smoke-001 --force-lock
python main.py collect --run results/<run_id>
python main.py report --run results/<run_id>
```

Для advanced/internal full-shape профилей остаются:

```bash
python main.py dry-run --config configs/config.example.yaml --limit 1
python main.py run --config configs/config.example.yaml --limit 1
```

Без `--limit` полный конфиг обрабатывает все изображения из `ImgToTag/` всеми настроенными моделями и режимами.

Для небольшой проверки reasoning-профилей REST используйте:

```bash
python main.py validate-config --config configs/config.rest-reasoning-smoke.yaml
python main.py run --config configs/config.rest-reasoning-smoke.yaml --run-id rest-reasoning-e2e-v4
```

## Документация

- [PROJECT_GUIDE.md](PROJECT_GUIDE.md) — основная навигация по проекту, каталогам, конфигам и результатам.
- [ARCHITECTURE.md](ARCHITECTURE.md) — архитектурный контракт v1: сущности, форматы, ограничения.
- [AGENTS.md](AGENTS.md) — инструкция для coding agents: что читать и какие проверки запускать.
- [specs/README.md](specs/README.md) — workflow спецификаций.
- [pools/README.md](pools/README.md) — форматы файлов tag pools.

## Двухуровневая конфигурация

Проект поддерживает два уровня:

- `config.yaml` — простой пользовательский профиль запуска;
- full internal config — развёрнутый словарь, который автоматически строится из `config.yaml` и потребляется текущим `BenchmarkConfig`/runner.

LM Studio URL в simple-config не настраивается: используются дефолты `http://localhost:1234/api/v1` и `http://localhost:1234/v1`.

## Что сравнивается

Проект помогает вручную и таблично оценивать:

- качество тегов;
- скорость ответа;
- стабильность формата ответа;
- соблюдение фиксированного пула тегов;
- количество тегов вне пула;
- ошибки загрузки модели и выполнения запроса;
- диагностику context length, token usage и VRAM;
- различия между моделями и квантованиями.

## Режимы тегирования

Для каждой картинки модель может получить до шести независимых запросов:

- `ru_free` — русские теги без фиксированного пула;
- `ru_pool` — русские теги только из plain-пула;
- `ru_pool_explained` — русские ID из explained-пула;
- `en_free` — английские теги без фиксированного пула;
- `en_pool` — английские теги только из plain-пула;
- `en_pool_explained` — английские ID из explained-пула.

Внутренний результат всегда нормализуется в JSON. Для `*_pool_explained` режимов модель отвечает ID тегов, а runner мапит ID обратно в канонические имена тегов.

Важно: reasoning-блоки из REST ответа сохраняются только как диагностика и никогда не парсятся как теги. Для парсинга используется только `final_content`; если модель записывает ход рассуждения прямо в `final_content`, line-parser отбрасывает такие служебные строки и оставляет только кандидаты в теги.

Текущий активный формат промптов:

- `ru_free`, `en_free`, `ru_pool`, `en_pool` — ответ одной строкой на тег (`line_tags`);
- `ru_pool_explained`, `en_pool_explained` — ответ одной строкой на ID (`line_ids`).

Поддержка `strict_json` сохранена в парсере и может использоваться в альтернативных конфигурациях.

## Выходные данные

Каждый запуск создает отдельную папку:

```text
results/<run_id>/
  run_config.yaml
  models.json
  summary.csv
  report.html
  errors.log
  run_manifest.json
  run_state.json
  run_complete.json
  requests/
  raw/
  normalized/
  assets/thumbs/
```

Главные файлы:

- `report.html` — основной HTML-отчет в формате answer matrix (image x mode x model -> answer);
- `report.html` содержит компактную верхнюю статистику (complete/partial, latency summary по запросам и изображениям) и print-friendly CSS;
- `report.html` рисует free-mode теги светло-синим, совпадения с pool светло-зеленым, out-of-pool теги светло-красным, а ошибки запроса/нормализации отдельным оранжевым цветом;
- `summary.csv` — таблица для Excel и дальнейшего анализа;
- `raw/` — сырые ответы LM Studio;
- `normalized/` — нормализованные ответы, ошибки и диагностические поля;
- `errors.log` — служебные события runner-а, включая cleanup загруженных моделей.

После введения request-artifacts источником истины являются `requests/<request_id>/*`.  
`summary.csv`, `diagnostics.json`, `report.html` и `diagnostics.html` — производные файлы, которые можно пересобрать через `collect/report`.

Режимы результата:

- `runtime.result_mode: deterministic` — один каноничный результат на logical request;
- `runtime.result_mode: overwrite` — принудительный пересчет каноничных файлов;
- `runtime.result_mode: accumulate` — append-only попытки в `requests/<request_id>/attempts/NNN/`.

## Ограничения v1

Проект остается простым CLI benchmark. В v1 не входят GUI, web-server, SQLite, async runner, judge-модель, plugin-system и поддержка backend-ов кроме LM Studio.

## Reports

- `report.html` is the primary answer matrix (`image x mode x model`).
- `diagnostics.html` is the secondary technical diagnostics page.
- `python main.py report --run results/<run_id>` refreshes both pages when `diagnostics.json` exists.



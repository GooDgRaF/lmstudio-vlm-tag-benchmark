# Local VLM Image Tagger Benchmark

CLI-проект для сравнения локальных vision-language моделей в LM Studio на задаче автоматического тегирования изображений.

Основной сценарий:

```text
ImgToTag/ -> python main.py run --config config.smoke.yaml -> results/<run_id>/report.html
```

Проект ориентирован на воспроизводимый локальный benchmark: он загружает выбранные модели, отправляет изображения с промптами, сохраняет сырые ответы, нормализованные результаты, CSV-сводку и статический HTML-отчет.

## Быстрый старт

1. Запустите LM Studio server на `localhost:1234`.
2. Положите изображения в папку `ImgToTag/`.
3. Выполните smoke-прогон:

```bash
python main.py run --config config.smoke.yaml
```

Smoke-конфиг использует одну модель и одну картинку. Это основной быстрый способ проверить вертикальный слайс проекта без полного прогона всех моделей.

После завершения откройте:

```text
results/<run_id>/report.html
```

## Основные команды

```bash
python main.py validate-config --config config.smoke.yaml
python main.py dry-run --config config.smoke.yaml
python main.py run --config config.smoke.yaml
python main.py report --run results/<run_id>
```

Для полного набора моделей используется:

```bash
python main.py dry-run --config config.example.yaml --limit 1
python main.py run --config config.example.yaml --limit 1
```

Без `--limit` полный конфиг обрабатывает все изображения из `ImgToTag/` всеми настроенными моделями и режимами.

## Документация

- [PROJECT_GUIDE.md](PROJECT_GUIDE.md) — основная навигация по проекту, каталогам, конфигам и результатам.
- [ARCHITECTURE.md](ARCHITECTURE.md) — архитектурный контракт v1: сущности, форматы, ограничения.
- [AGENTS.md](AGENTS.md) — инструкция для coding agents: что читать и какие проверки запускать.
- [specs/README.md](specs/README.md) — workflow спецификаций.
- [pools/README.md](pools/README.md) — форматы файлов tag pools.

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
  raw/
  normalized/
  assets/thumbs/
```

Главные файлы:

- `report.html` — основной HTML-отчет в формате answer matrix (image x mode x model -> answer);
- `summary.csv` — таблица для Excel и дальнейшего анализа;
- `raw/` — сырые ответы LM Studio;
- `normalized/` — нормализованные ответы, ошибки и диагностические поля;
- `errors.log` — служебные события runner-а, включая cleanup загруженных моделей.

## Ограничения v1

Проект остается простым CLI benchmark. В v1 не входят GUI, web-server, SQLite, async runner, judge-модель, plugin-system и поддержка backend-ов кроме LM Studio.

## Reports

- `report.html` is the primary answer matrix (`image x mode x model`).
- `diagnostics.html` is the secondary technical diagnostics page.
- `python main.py report --run results/<run_id>` refreshes both pages when `diagnostics.json` exists.


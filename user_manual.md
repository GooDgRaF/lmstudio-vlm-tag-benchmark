# User Manual (Short)

## 1. Что делает проект

Проект прогоняет локальные VLM-модели через LM Studio на изображениях и сохраняет:
- сырые ответы (`raw`);
- нормализованные ответы (`normalized`);
- сводку (`summary.csv`);
- HTML-отчеты (`report.html`, `diagnostics.html`).

Основной transport: LM Studio REST Chat (`/api/v1/chat`).

## 2. Перед запуском

1. Запустите LM Studio server (`localhost:1234`).
2. Убедитесь, что нужные модели скачаны в LM Studio.
3. Положите изображения в папку (обычно `ImgToTag/`).

## 3. Основные конфиги

- `config.smoke.yaml` — быстрый smoke (обычно 1 модель, 1 изображение).
- `config.example.yaml` — полный benchmark (много моделей/режимов).
- `config.rest-reasoning-smoke.yaml` — маленький e2e для сравнения `reasoning: on/off`.

## 4. Как настраивать конфиг

Ключевые поля:

- `input.image_dir` — папка с картинками.
- `modes` — режимы (`ru_free`, `ru_pool`, `ru_pool_explained`, `en_free`, `en_pool`, `en_pool_explained`).
- `models[]` — список моделей.
  - `id` и `base_model_id` — id модели в LM Studio.
  - `label` — уникальное имя в отчетах.
  - `reasoning` — `default` / `on` / `off`.
- `generation.max_tokens` — лимит output токенов.
- `load.context_length` — контекст модели.
- `limits.limit_images` — ограничение числа изображений (`null` = все).
- `runtime.image_request_smoke_test` — включить/выключить pre-smoke на модель.

## 5. Базовые команды

Проверка конфига:

```bash
python main.py validate-config --config config.smoke.yaml
```

Проверка плана прогона (без реального инференса):

```bash
python main.py dry-run --config config.smoke.yaml
```

Запуск benchmark:

```bash
python main.py run --config config.smoke.yaml
```

Запуск с фиксированным run id:

```bash
python main.py run --config config.example.yaml --run-id my-run-001
```

Пересборка сводки и отчетов из артефактов:

```bash
python main.py collect --run results/<run_id> --write-reports
```

Только пересборка HTML:

```bash
python main.py report --run results/<run_id>
```

## 6. Где смотреть результат

После запуска:

- `results/<run_id>/report.html` — основная матрица ответов.
- `results/<run_id>/diagnostics.html` — тех-диагностика.
- `results/<run_id>/summary.csv` — табличная сводка.
- `results/<run_id>/requests/<request_id>/raw.json` — сырой ответ LM Studio.
- `results/<run_id>/requests/<request_id>/normalized.json` — нормализованный ответ.

## 7. Важные интерпретации

- `no_final_answer` = модель выдала reasoning, но не выдала финальный ответ с тегами.
- `output_truncated` = модель уперлась в лимит output токенов.
- `pool_validation_failed` = ответ содержит теги/ID вне выбранного пула (это сигнал качества, не обязательно баг).

## 8. Рекомендуемый рабочий цикл

1. Правите конфиг.
2. `validate-config`.
3. `dry-run`.
4. Небольшой `run` (например smoke или `--limit 1`).
5. Смотрите `report.html` + `summary.csv`.
6. При необходимости `collect --write-reports` для пересборки.


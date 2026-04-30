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

## 3. Основной пользовательский путь (через `config.yaml`)

1. Сгенерируйте пользовательский конфиг:

```bash
python main.py init-config
```

2. Откройте `config.yaml` и настройте запуск:
- в `models:` оставьте активными нужные label моделей (остальные строки можно закомментировать);
- в `modes:` оставьте нужные режимы;
- при необходимости поменяйте `images_folder`, `limit_images`, `output_folder`.

3. Проверьте план без инференса:

```bash
python main.py dry-run --config config.yaml
```

4. Запустите benchmark:

```bash
python main.py run --config config.yaml
```

`dry-run` только валидирует/планирует. `run` делает реальные запросы к LM Studio и пишет результаты в `results/`.

## 4. Минимальные поля в `config.yaml`

Обязательные:
- `images_folder`
- `models`
- `modes`

Часто используемые опциональные:
- `limit_images`
- `output_folder`
- `context_length`
- `max_output_tokens`
- `temperature`
- `recursive`

## 5. Базовые команды

Инициализация/обновление:

```bash
python main.py init-config
python main.py refresh-models
python main.py list-models
```

Проверка и запуск:

```bash
python main.py validate-config --config config.yaml
python main.py dry-run --config config.yaml
python main.py run --config config.yaml
```

Запуск с фиксированным run id:

```bash
python main.py run --config config.yaml --run-id my-run-001
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

## 8. Дополнительные full-shape конфиги

Для внутренней/расширенной работы в репо есть готовые full-shape профили:
- `configs/config.smoke.yaml` — быстрый smoke (обычно 1 модель, 1 изображение).
- `configs/config.example.yaml` — полный benchmark (много моделей/режимов).
- `configs/config.rest-reasoning-smoke.yaml` — маленький e2e для сравнения `reasoning: on/off`.

## 9. Рекомендуемый рабочий цикл

1. `python main.py init-config`
2. Правите `config.yaml`.
3. `validate-config`.
4. `dry-run`.
5. Небольшой `run`.
6. Смотрите `report.html` + `summary.csv`.
7. При необходимости `collect --write-reports` для пересборки.

# Local VLM Image Tagger Benchmark

Локальный CLI-проект для сравнения vision-language моделей в LM Studio на задаче автоматического тегирования изображений.

Проект не является production-сервисом. Его цель — простой воспроизводимый benchmark: взять папку изображений, прогнать выбранные локальные VLM, сохранить ответы и сравнить модели глазами по HTML-отчету и таблице `summary.csv`.

## Текущий сценарий

Изображения берутся из папки:

```text
F:\Works\Иные проекты\Local VLM benchmark\ImgToTag
```

Все изображения, которые будут положены в эту папку, попадают в полный прогон. Для быстрых тестовых запусков можно ограничиться одной картинкой через CLI-опцию `--limit 1`.

## Что сравнивается

Важны все основные критерии:

- качество тегов при ручном просмотре;
- скорость ответа;
- стабильность формата ответа;
- соблюдение фиксированного пула тегов;
- количество тегов вне пула;
- ошибки загрузки модели, ответа модели и выгрузки модели;
- различия между квантизациями;
- диагностические признаки нехватки контекста или памяти.

## Модели

В активный пример конфига включены локальные модели из LM Studio, которые одновременно:

- являются LLM;
- имеют `vision: true`;
- меньше 20B параметров.

Важно: считаются не только базовые модели, но и варианты квантизации.

```text
5 базовых моделей
8 тестируемых model variants с учетом квантизаций
```

Активный список:

```text
models/models.active.yaml
```

Исключенные модели с причинами:

```text
models/models.excluded.yaml
```

Полный исходный экспорт LM Studio:

```text
models/lmstudio-models.raw.json
```

## Режимы тегирования

Для каждой картинки можно выполнить до 6 независимых запросов:

1. `ru_free` — модель сама придумывает русские теги;
2. `ru_pool` — модель выбирает русские теги только из фиксированного пула;
3. `ru_pool_explained` — модель выбирает русские теги из пула с пояснениями;
4. `en_free` — модель сама придумывает английские теги;
5. `en_pool` — модель выбирает английские теги только из фиксированного пула;
6. `en_pool_explained` — модель выбирает английские теги из пула с пояснениями.

## Форматы ответа модели

Внутренний нормализованный результат программы всегда хранится как JSON.

Но сама модель не обязана всегда возвращать JSON. Это сделано специально для маленьких моделей.

### Free/plain modes

Основной формат:

```json
{"tags": ["tag1", "tag2"]}
```

Fallback-формат:

```text
tag1
tag2
tag3
```

Программа сама преобразует line-format во внутренний JSON.

### Explained pool modes

Для explained-pools основной формат ответа — не теги, а ID тегов:

```text
RU001
RU017
RU054
```

или:

```text
EN001
EN017
EN054
```

Это надежнее для маленьких моделей, потому что им не нужно перепечатывать длинные теги со слешами, пробелами, скобками и пояснениями. Программа сама мапит ID обратно в исходный тег.

Максимум — 10 тегов. Если модель не уверена, лучше не ставить тег.

## Файлы тегов

Runner v1 использует только четыре pool-файла:

```text
pools/ru_plain.txt
pools/en_plain.txt
pools/ru_explained_ids.tsv
pools/en_explained_ids.tsv
```

Plain-файлы используют формат:

```text
один тег на строку
```

Explained ID TSV использует формат:

```text
id<TAB>tag<TAB>explanation
```

Например:

```text
RU001<TAB>Общий<TAB>Безопасно для всех.
EN001<TAB>General<TAB>Safe for all audiences.
```

Prompt для explained-pool режимов программа генерирует на лету из TSV:

```text
[RU001] Общий — Безопасно для всех.
[EN001] General — Safe for all audiences.
```

Отдельные `*_prompt.txt`, JSON-копии и legacy converted-файлы в `pools/` не хранятся. 

Подробности конвертации — в `TAG_POOL_CONVERSION.md`.

## Контекст и диагностика

`context_length` задается параметром конфига:

```yaml
load:
  context_length: 16384
```

Программа должна сохранять диагностику:

- запрошенный `context_length`;
- фактически примененный `context_length` из ответа LM Studio, если доступен;
- `usage.prompt_tokens`, `usage.completion_tokens`, `usage.total_tokens`, если API их вернул;
- `finish_reason`;
- признаки `context_overflow`, `context_near_limit`, `output_truncated`;
- память GPU до/после загрузки модели через `nvidia-smi`, если команда доступна;
- ошибку загрузки модели, если модель не влезла или LM Studio отказал в загрузке.

Диагностика не должна ломать запуск, если `nvidia-smi` недоступен. В таком случае поле просто помечается как `gpu_diagnostics_available: false`.

## Основные команды будущей программы

```bash
python main.py list-models --config config.example.yaml
python main.py validate-config --config config.example.yaml
python main.py dry-run --config config.example.yaml
python main.py run --config config.example.yaml
python main.py run --config config.example.yaml --limit 1
python main.py report --run results/<run_id>
```

Для smoke-проверки используйте только самую маленькую модель:

```bash
python main.py run --config config.smoke.yaml --limit 1
python main.py report --run results/<run_id>
```

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

- `report.html` — основной отчет для просмотра глазами;
- `summary.csv` — таблица для Excel;
- `raw/` — сырые ответы моделей;
- `normalized/` — нормализованные результаты и диагностические поля.

## Ограничения v1

В первой версии не нужны:

- GUI;
- база данных;
- веб-сервер;
- многопоточный инференс;
- judge-модель;
- поддержка backend кроме LM Studio;
- сложный frontend;
- plugin-system.

Цель v1 — простая, надежная и проверяемая программа для локального сравнения VLM.

# Архитектура v5: Local VLM Image Tagger Benchmark

## 1. Назначение

Проект нужен для локального сравнения vision-language моделей через LM Studio на задаче тегирования изображений.

Это не production-теггер и не большая ML-платформа. Первая версия должна быть простой CLI-программой, которая:

1. читает конфиг;
2. берет изображения из указанной папки;
3. по очереди загружает локальные VLM в LM Studio;
4. прогоняет картинки в нескольких режимах тегирования;
5. сохраняет сырой ответ, нормализованный ответ и диагностику;
6. пишет `summary.csv` инкрементально после каждого запроса;
7. строит статический `report.html`;
8. выгружает модель и переходит к следующей.

## 2. Данные пользователя

Папка изображений:

```text
F:\Works\Иные проекты\Local VLM benchmark\ImgToTag
```

Полный прогон обрабатывает все изображения из папки. Тестовый прогон может ограничиваться одной картинкой через `--limit 1`.

Расширения v1:

```text
.jpg, .jpeg, .png, .webp, .bmp
```

Рекурсивный обход по умолчанию выключен.

## 3. Модели

Исходный список моделей получен из `lmstudio-models.json`. В активный конфиг попадают только модели:

- `type: llm`;
- `vision: true`;
- меньше 20B параметров.

Активные модели сохранены в `models/models.active.yaml`.

Исключаются:

- модели 20B+;
- non-vision модели;
- embedding-модели.

Квантизация учитывается явно через поля:

```yaml
id: "qwen/qwen3-vl-8b@q4_k_m"
base_model_id: "qwen/qwen3-vl-8b"
label: "qwen3-vl-8b-q4_k_m"
params: "8B"
quant: "Q4_K_M"
quant_bits: 4
```

Важно различать:

```text
5 базовых моделей
8 тестируемых model variants с учетом квантизаций
```

Если в LM Studio позже будут скачаны другие варианты квантизации, их нужно добавить отдельными строками в `models`.

## 4. LM Studio API

Архитектура разделяет два endpoint-направления.

Native LM Studio REST API используется для управления моделями:

```text
GET  /api/v1/models
POST /api/v1/models/load
POST /api/v1/models/unload
```

Для выгрузки модельного экземпляра `POST /api/v1/models/unload` ожидает строго тело
`{"instance_id": "<loaded instance id>"}`. Не добавлять соседний ключ `id`: текущий
LM Studio отвергает лишние ключи ошибкой `unrecognized_keys`. Значение
`instance_id` нужно брать из ответа `load` или из элементов `loaded_instances`
в `GET /api/v1/models`; оно может иметь вид `qwen/qwen3-vl-4b` или
`qwen/qwen3-vl-4b:2` и не обязано совпадать с variant-id из конфига.

OpenAI-compatible API используется для запросов к модели:

```text
POST /v1/chat/completions (legacy compatibility path)
```

Основной inference transport в текущем benchmark — LM Studio REST Chat:

```text
POST /api/v1/chat
```

`reasoning_content` из REST-ответа считается диагностическими данными и не используется для парсинга тегов.

В конфиге это хранится раздельно:

```yaml
lmstudio:
  host: "http://localhost:1234"
  api_base_url: "http://localhost:1234/api/v1"
  openai_base_url: "http://localhost:1234/v1"
  api_key: "lm-studio"
```

## 5. Термины модели

Нельзя смешивать ID модели, подпись модели и ID загруженного экземпляра.

Используем:

- `id` — конкретный variant-id модели, например `qwen/qwen3-vl-8b@q4_k_m`;
- `base_model_id` — базовый ID модели, например `qwen/qwen3-vl-8b`;
- `label` — стабильное имя для файлов и отчетов;
- `instance_id` — ID загруженного экземпляра, полученный после `load`;
- `quant` — человеко-читаемая квантизация;
- `quant_bits` — число бит, если известно.

Минимальный объект `LoadedModel`:

```python
@dataclass
class LoadedModel:
    id: str
    base_model_id: str
    label: str
    instance_id: str
    params: str | None
    quant: str | None
    quant_bits: int | None
    requested_context_length: int | None
    actual_context_length: int | None
    load_config: dict
```

## 6. Минимальная структура проекта

```text
vlm-image-tagger/
  README.md
  ARCHITECTURE.md
  config.example.yaml
  TAG_POOL_CONVERSION.md
  requirements.txt
  main.py

  src/
    config.py
    lmstudio_client.py
    image_loader.py
    tag_pools.py
    prompts.py
    validator.py
    runner.py
    diagnostics.py
    storage.py
    report.py

  pools/
    README.md
    ru_plain.txt
    en_plain.txt
    ru_explained_ids.tsv
    en_explained_ids.tsv

  models/
    models.active.yaml
    models.excluded.yaml
    lmstudio-models.raw.json

  results/
    .gitkeep
```

`model_registry.py` не нужен как обязательный модуль. Сопоставление моделей можно держать в `config.py` или `runner.py`, чтобы не создавать лишнюю подсистему.

## 7. Файлы тегов

В архиве лежат уже нормализованные файлы.

### 7.1. Plain pools

Формат:

```text
один тег на строку
```

Файлы:

```text
pools/ru_plain.txt
pools/en_plain.txt
```

Парсер:

- читает строки;
- trim;
- пропускает пустые строки;
- пропускает строки, начинающиеся с `#`;
- сохраняет регистр и символы тега.

### 7.2. Explained pools

Runner v1 должен использовать ID-формат, а не просить модель перепечатывать сами теги.

Файлы:

```text
pools/ru_explained_ids.tsv
pools/en_explained_ids.tsv
```

Формат TSV:

```text
id<TAB>tag<TAB>explanation
```

Пример:

```text
RU001<TAB>Общий<TAB>Безопасно для всех.
EN001<TAB>General<TAB>Safe for all audiences.
```

Prompt-ready текст не хранится отдельными файлами. Runner генерирует его на лету из TSV:

```text
[RU001] Общий — Безопасно для всех.
[EN001] General — Safe for all audiences.
```

JSON-копии и legacy converted-файлы в `pools/` не нужны для v1. Если они понадобятся для отладки, их можно сгенерировать отдельно скриптом конвертации, но они не входят в нормальный архитектурный пакет.

## 8. Режимы тегирования

```text
ru_free	ru tags, модель сама придумывает теги
ru_pool	ru tags, выбор из plain pool
ru_pool_explained	ru IDs, выбор из explained ID pool
en_free	en tags, модель сама придумывает теги
en_pool	en tags, выбор из plain pool
en_pool_explained	en IDs, выбор из explained ID pool
```

Общие правила:

- максимум 10 тегов;
- если модель не уверена, лучше не ставить тег;
- не возвращать описание картинки;
- не использовать Markdown;
- не добавлять пояснения;
- в pool-режимах использовать только элементы из указанного пула.

## 9. Форматы ответа модели

Внутренний результат программы всегда нормализуется в JSON. Формат ответа модели может быть разным.

### 9.1. `strict_json`

Основной формат для сильных моделей и обычных режимов:

```json
{"tags": ["tag1", "tag2"]}
```

Можно использовать `response_format` с JSON Schema.

### 9.2. `line_tags`

Fallback для `free` и `plain_pool` режимов:

```text
tag1
tag2
tag3
```

Программа превращает строки во внутренний JSON.

### 9.3. `line_ids`

Основной формат для `*_pool_explained` режимов:

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

Программа валидирует ID, затем мапит их обратно в теги.

## 10. JSON и валидация

Для `strict_json` минимальная схема:

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "image_tags",
    "strict": true,
    "schema": {
      "type": "object",
      "properties": {
        "tags": {
          "type": "array",
          "items": {"type": "string"},
          "maxItems": 10
        }
      },
      "required": ["tags"]
    }
  }
}
```

Fallback допускается, но должен фиксироваться диагностически:

1. обычный prompt с требованием JSON;
2. извлечение первого JSON-объекта из ответа;
3. line-format fallback;
4. repair только на уровне парсинга, без скрытия нарушений пула.

Нормализованный результат должен хранить:

```json
{
  "raw_output": "...",
  "response_format_requested": "strict_json",
  "response_format_used": "line_ids",
  "raw_tags": ["..."],
  "raw_ids": ["RU001"],
  "accepted_tags": ["..."],
  "accepted_ids": ["RU001"],
  "rejected_tags": ["..."],
  "rejected_ids": ["RU999"],
  "parse_ok": true,
  "schema_ok": true,
  "json_extracted": false,
  "line_fallback_used": false,
  "pool_ok": true,
  "pool_violations": 0,
  "error_type": null,
  "error": null
}
```

## 11. Context length и диагностика

`context_length` должен быть параметром, а не захардкоженной константой.

Базовый конфиг:

```yaml
load:
  context_length: 16384
  flash_attention: true
  offload_kv_cache_to_gpu: true
  echo_load_config: true
```

Проверки:

1. До загрузки модели сравнить `load.context_length` с `model.max_context_length` из конфига или `GET /api/v1/models`.
2. Если запрошенный context больше известного максимума модели, это ошибка конфигурации.
3. После загрузки сохранить `load_config.context_length`, если LM Studio его вернул.
4. В каждом ответе сохранить `usage.prompt_tokens`, `usage.completion_tokens`, `usage.total_tokens`, если они есть.
5. Если API вернул ошибку про превышение контекста, классифицировать ее как `context_overflow`.
6. Если `usage.total_tokens` близко к фактическому контексту, помечать `context_near_limit`.
7. Если `finish_reason == "length"`, помечать `output_truncated`.

Рекомендуемые пороги:

```yaml
diagnostics:
  context_warning_ratio: 0.85
  context_error_ratio: 0.97
```

`context_near_limit` не должен считаться фатальной ошибкой. Это предупреждение для отчета.

## 12. Диагностика GPU/VRAM

Программа не должна пытаться идеально предсказывать, влезет ли модель в VRAM. Надежнее фиксировать факты.

Минимальная диагностика:

1. Перед загрузкой модели выполнить `nvidia-smi`, если он доступен.
2. После загрузки модели выполнить `nvidia-smi` еще раз.
3. Сохранить total/used/free VRAM до и после загрузки.
4. Если загрузка модели упала, сохранить ошибку LM Studio как `load_failed`.
5. Если текст ошибки похож на нехватку памяти, классифицировать как `load_failed_oom`.
6. Если `nvidia-smi` недоступен, не падать, а записать `gpu_diagnostics_available: false`.

Это достаточно для v1. NVML-библиотеку добавлять не нужно.

## 13. Проверка image API

Перед полным прогоном модели выполняется `image_request_smoke_test`:

1. загрузить модель;
2. отправить маленький запрос с изображением;
3. проверить, что API не падает и ответ можно обработать.

Этот тест проверяет только способность модели/API принять изображение. Он не оценивает качество зрения.

## 14. Формат отправки изображения

Для OpenAI-compatible `/v1/chat/completions` использовать message content с текстом и картинкой:

```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "...prompt..."},
    {
      "type": "image_url",
      "image_url": {
        "url": "data:image/png;base64,..."
      }
    }
  ]
}
```

Если изображение слишком большое, можно создать временную уменьшенную копию для запроса. В отчете и `summary.csv` сохранять путь к оригинальному файлу.

## 15. Основной цикл

```text
read config
check LM Studio availability
list LM Studio models
validate model ids
load tag pools
find images
create results/<run_id>/
create summary.csv header

for each model:
    collect gpu diagnostics before load
    load model with configured context_length
    collect gpu diagnostics after load
    save requested and actual load config
    run image_request_smoke_test
    if smoke test failed:
        save model error
        unload model
        continue

    for each image:
        for each mode:
            build prompt
            call model
            save raw response
            normalize and validate response
            save token/context diagnostics
            save normalized json
            append summary.csv row immediately

    unload model

build report.html
```

Запуск последовательный. Параллельность в v1 не нужна.

## 16. Resume

Простой resume без базы данных:

```text
если normalized/<request_id>.json существует и это успешный результат — пропустить;
если normalized/<request_id>.json содержит ошибку — можно повторить.
```

Конфиг:

```yaml
runtime:
  resume: true
  skip_existing_success: true
  retry_existing_errors: true
```

## 17. Summary CSV

Одна строка — один запрос к модели.

Рекомендуемые поля:

```csv
run_id,request_id,model_id,base_model_id,model_label,params,quant,quant_bits,image_id,image_path,mode,response_format_requested,response_format_used,accepted_tags,accepted_ids,rejected_tags,rejected_ids,tag_count,pool_violations,parse_ok,schema_ok,json_extracted,line_fallback_used,pool_ok,latency_sec,prompt_tokens,completion_tokens,total_tokens,requested_context_length,actual_context_length,context_near_limit,context_overflow,output_truncated,gpu_memory_before_mb,gpu_memory_after_mb,error_type,error
```

## 18. HTML report

Статический HTML без backend и без React.

Минимально нужны:

- сводка по моделям;
- среднее время ответа;
- процент `parse_ok`;
- процент `schema_ok`;
- процент `line_fallback_used`;
- нарушения пула;
- ошибки;
- context warnings;
- load/VRAM diagnostics;
- галерея: картинка + ответы моделей рядом.

## 19. Что не делать в v1

Не добавлять:

- GUI;
- SQLite;
- веб-сервер;
- async runner;
- judge-модель;
- поддержку Ollama;
- plugin-system;
- тяжелую frontend-сборку;
- автоматические метрики качества без эталонной разметки.

Проект должен остаться простым.

# User Manual (Short)

## 1. Р§С‚Рѕ РґРµР»Р°РµС‚ РїСЂРѕРµРєС‚

РџСЂРѕРµРєС‚ РїСЂРѕРіРѕРЅСЏРµС‚ Р»РѕРєР°Р»СЊРЅС‹Рµ VLM-РјРѕРґРµР»Рё С‡РµСЂРµР· LM Studio РЅР° РёР·РѕР±СЂР°Р¶РµРЅРёСЏС… Рё СЃРѕС…СЂР°РЅСЏРµС‚:
- СЃС‹СЂС‹Рµ РѕС‚РІРµС‚С‹ (`raw`);
- РЅРѕСЂРјР°Р»РёР·РѕРІР°РЅРЅС‹Рµ РѕС‚РІРµС‚С‹ (`normalized`);
- СЃРІРѕРґРєСѓ (`summary.csv`);
- HTML-РѕС‚С‡РµС‚С‹ (`report.html`, `diagnostics.html`).

РћСЃРЅРѕРІРЅРѕР№ transport: LM Studio REST Chat (`/api/v1/chat`).

## 2. РџРµСЂРµРґ Р·Р°РїСѓСЃРєРѕРј

1. Р—Р°РїСѓСЃС‚РёС‚Рµ LM Studio server (`localhost:1234`).
2. РЈР±РµРґРёС‚РµСЃСЊ, С‡С‚Рѕ РЅСѓР¶РЅС‹Рµ РјРѕРґРµР»Рё СЃРєР°С‡Р°РЅС‹ РІ LM Studio.
3. РџРѕР»РѕР¶РёС‚Рµ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РІ РїР°РїРєСѓ (РѕР±С‹С‡РЅРѕ `ImgToTag/`).

## 3. РћСЃРЅРѕРІРЅС‹Рµ РєРѕРЅС„РёРіРё

- `configs/config.smoke.yaml` вЂ” Р±С‹СЃС‚СЂС‹Р№ smoke (РѕР±С‹С‡РЅРѕ 1 РјРѕРґРµР»СЊ, 1 РёР·РѕР±СЂР°Р¶РµРЅРёРµ).
- `configs/config.example.yaml` вЂ” РїРѕР»РЅС‹Р№ benchmark (РјРЅРѕРіРѕ РјРѕРґРµР»РµР№/СЂРµР¶РёРјРѕРІ).
- `configs/config.rest-reasoning-smoke.yaml` вЂ” РјР°Р»РµРЅСЊРєРёР№ e2e РґР»СЏ СЃСЂР°РІРЅРµРЅРёСЏ `reasoning: on/off`.

## 4. РљР°Рє РЅР°СЃС‚СЂР°РёРІР°С‚СЊ РєРѕРЅС„РёРі

РљР»СЋС‡РµРІС‹Рµ РїРѕР»СЏ:

- `input.image_dir` вЂ” РїР°РїРєР° СЃ РєР°СЂС‚РёРЅРєР°РјРё.
- `modes` вЂ” СЂРµР¶РёРјС‹ (`ru_free`, `ru_pool`, `ru_pool_explained`, `en_free`, `en_pool`, `en_pool_explained`).
- `models[]` вЂ” СЃРїРёСЃРѕРє РјРѕРґРµР»РµР№.
  - `id` Рё `base_model_id` вЂ” id РјРѕРґРµР»Рё РІ LM Studio.
  - `label` вЂ” СѓРЅРёРєР°Р»СЊРЅРѕРµ РёРјСЏ РІ РѕС‚С‡РµС‚Р°С….
  - `reasoning` вЂ” `default` / `on` / `off`.
- `generation.max_tokens` вЂ” Р»РёРјРёС‚ output С‚РѕРєРµРЅРѕРІ.
- `load.context_length` вЂ” РєРѕРЅС‚РµРєСЃС‚ РјРѕРґРµР»Рё.
- `limits.limit_images` вЂ” РѕРіСЂР°РЅРёС‡РµРЅРёРµ С‡РёСЃР»Р° РёР·РѕР±СЂР°Р¶РµРЅРёР№ (`null` = РІСЃРµ).
- `runtime.image_request_smoke_test` вЂ” РІРєР»СЋС‡РёС‚СЊ/РІС‹РєР»СЋС‡РёС‚СЊ pre-smoke РЅР° РјРѕРґРµР»СЊ.

## 5. Р‘Р°Р·РѕРІС‹Рµ РєРѕРјР°РЅРґС‹

РџСЂРѕРІРµСЂРєР° РєРѕРЅС„РёРіР°:

```bash
python main.py validate-config --config configs/config.smoke.yaml
```

РџСЂРѕРІРµСЂРєР° РїР»Р°РЅР° РїСЂРѕРіРѕРЅР° (Р±РµР· СЂРµР°Р»СЊРЅРѕРіРѕ РёРЅС„РµСЂРµРЅСЃР°):

```bash
python main.py dry-run --config configs/config.smoke.yaml
```

Р—Р°РїСѓСЃРє benchmark:

```bash
python main.py run --config configs/config.smoke.yaml
```

Р—Р°РїСѓСЃРє СЃ С„РёРєСЃРёСЂРѕРІР°РЅРЅС‹Рј run id:

```bash
python main.py run --config configs/config.example.yaml --run-id my-run-001
```

РџРµСЂРµСЃР±РѕСЂРєР° СЃРІРѕРґРєРё Рё РѕС‚С‡РµС‚РѕРІ РёР· Р°СЂС‚РµС„Р°РєС‚РѕРІ:

```bash
python main.py collect --run results/<run_id> --write-reports
```

РўРѕР»СЊРєРѕ РїРµСЂРµСЃР±РѕСЂРєР° HTML:

```bash
python main.py report --run results/<run_id>
```

## 6. Р“РґРµ СЃРјРѕС‚СЂРµС‚СЊ СЂРµР·СѓР»СЊС‚Р°С‚

РџРѕСЃР»Рµ Р·Р°РїСѓСЃРєР°:

- `results/<run_id>/report.html` вЂ” РѕСЃРЅРѕРІРЅР°СЏ РјР°С‚СЂРёС†Р° РѕС‚РІРµС‚РѕРІ.
- `results/<run_id>/diagnostics.html` вЂ” С‚РµС…-РґРёР°РіРЅРѕСЃС‚РёРєР°.
- `results/<run_id>/summary.csv` вЂ” С‚Р°Р±Р»РёС‡РЅР°СЏ СЃРІРѕРґРєР°.
- `results/<run_id>/requests/<request_id>/raw.json` вЂ” СЃС‹СЂРѕР№ РѕС‚РІРµС‚ LM Studio.
- `results/<run_id>/requests/<request_id>/normalized.json` вЂ” РЅРѕСЂРјР°Р»РёР·РѕРІР°РЅРЅС‹Р№ РѕС‚РІРµС‚.

## 7. Р’Р°Р¶РЅС‹Рµ РёРЅС‚РµСЂРїСЂРµС‚Р°С†РёРё

- `no_final_answer` = РјРѕРґРµР»СЊ РІС‹РґР°Р»Р° reasoning, РЅРѕ РЅРµ РІС‹РґР°Р»Р° С„РёРЅР°Р»СЊРЅС‹Р№ РѕС‚РІРµС‚ СЃ С‚РµРіР°РјРё.
- `output_truncated` = РјРѕРґРµР»СЊ СѓРїРµСЂР»Р°СЃСЊ РІ Р»РёРјРёС‚ output С‚РѕРєРµРЅРѕРІ.
- `pool_validation_failed` = РѕС‚РІРµС‚ СЃРѕРґРµСЂР¶РёС‚ С‚РµРіРё/ID РІРЅРµ РІС‹Р±СЂР°РЅРЅРѕРіРѕ РїСѓР»Р° (СЌС‚Рѕ СЃРёРіРЅР°Р» РєР°С‡РµСЃС‚РІР°, РЅРµ РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ Р±Р°Рі).

## 8. Р РµРєРѕРјРµРЅРґСѓРµРјС‹Р№ СЂР°Р±РѕС‡РёР№ С†РёРєР»

1. РџСЂР°РІРёС‚Рµ РєРѕРЅС„РёРі.
2. `validate-config`.
3. `dry-run`.
4. РќРµР±РѕР»СЊС€РѕР№ `run` (РЅР°РїСЂРёРјРµСЂ smoke РёР»Рё `--limit 1`).
5. РЎРјРѕС‚СЂРёС‚Рµ `report.html` + `summary.csv`.
6. РџСЂРё РЅРµРѕР±С…РѕРґРёРјРѕСЃС‚Рё `collect --write-reports` РґР»СЏ РїРµСЂРµСЃР±РѕСЂРєРё.



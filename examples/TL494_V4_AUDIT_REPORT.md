# TL494CN v4 — проверяемый отчёт MAIN 2 (Issue #107)

**Status: MODEL PASS / PRINT ROUTING FAIL / NO AFTER RELEASE.**  
Создано на основе `reference/tl494-native-rework-20261114` EXACT `e695c415fdced164b0e0c39c5249d030795a0aa6`. Исходные файлы сохранены, `main`/`integration` не изменены. Никаких PR не объединено.

## 1. Старые чертежи — BEFORE, неизменные

- [Чистый PNG старого листа](https://github.com/Tridgi/gost-schematic/blob/e695c415fdced164b0e0c39c5249d030795a0aa6/examples/tl494_named_truth_output/TL494_named_photo_clean.png)
- [Чистый SVG старого листа](https://github.com/Tridgi/gost-schematic/blob/e695c415fdced164b0e0c39c5249d030795a0aa6/examples/tl494_named_truth_output/TL494_named_photo_clean.svg)
- [Старый диагностический PNG](https://github.com/Tridgi/gost-schematic/blob/e695c415fdced164b0e0c39c5249d030795a0aa6/examples/tl494_named_truth_output/TL494_named_photo_diagnostic.png)
- Ширина/высота исходного SVG: **679.3 × 220.051 мм**. На превью 640 пикселей штрих 0.3мм ≈**0.2826px**. Это НЕ читаемый A3.

## 2. Новая модель: исправлено, но не объявлено готовым E3

- [План по 14 критериям](tl494_v4/RECONSTRUCTION_PLAN.md)
- [Неизменный реестр 23 BOM/15 Nets](tl494_v4/model_contract.py) и [actual source inventory](tl494_v4/evidence_runs/43608095630-1/source_inventory.json).
- 16 физических контактов TL494 привязаны к источнику, DA1.3 FEEDBACK `INPUT` по TI SLVS074J table4-1. Полное заводское имя сохранено, графический alias `FB`; DA1.13 `OUTPUT CTRL` сохранён, alias `OC`. Никакой автоматической обрезки.
- [Изолированный нативный адаптер](tl494_v4/engine_adapter.py) возвращает исходный каталоговый `transistor.mosfet_n_enh` без неутверждённого добавления графической точки. Три физических G/D/S сохраняются. Все C/L/VD/VT/R5/FU выбираются по точному `part_id` источника.
- [Предложение изменения исходного PAINT](tl494_v4/paint_rotation_patch.py) добавляет угол 270°, чтобы PWM читался снизу вверх; тело DA1 и все 16 физических точек неподвижны. Это **DRAFT**, требуется визуальная проверка PAINT/QA 0/90/270 и восьми D4.
- Общий провод `COMMON` — только схемный 0V, НЕ PE/корпус. Сохранение семантики утверждено. Знак земли/шасси не придуман вместо #109.

## 3. Численный DRC (истинная геометрия, не только ERC)

[Файл полного отчёта #108, с учётом геометрии УГО и измеренного OpenGost Type A](tl494_v4/evidence_runs/43608095630-1/full_stroke_and_text_drc.json). Вызван точный владелец `route_drc.py` из `parallel/electrical-routing-drc-tl494-cycle9`, SHA `9b0511303af806575040d6e48c87c0ed66236a90` — только read-only импорт на CI, **не слияние**.

| Пара проводов | Net 1 | Net 2 | Зазор между краями линий | Требуется |
|---|---|---|---:|---:|
| W56 — W72 | ERROR_INPUT | OSCILLATOR_CT | **0.70 мм** | ≥3 мм |
| W28 — W71 | COMMON | OSCILLATOR_CT | **1.45 мм** | ≥3 мм |
| W54 — W63 | SOFT_START | FEEDBACK | **1.70 мм** | ≥3 мм |
| W42 — W85 | CONTROL_REFERENCE | COMMON | **1.70 мм** | ≥3 мм |
| W27 — W62 | COMMON | FEEDBACK | **1.95 мм** | ≥3 мм |

**9 ERROR**, **32 WARNING**: 5 параллельных расстояний, 1 пересечение одного Net без установленной точки (W1/W86, x=30 мм, y=82 мм), 1 пересечение keepout корпуса X1 (W77), 2 пересечения реального графического штриха X1/DA1 (W77/W78). 32 других Net пересекаются Х-образно без электрического контакта; модель не объявляет их соединёнными, но печатная трассировка нуждается в маршрутизации/разрешении. Суммарная длина: **4691.25 мм**, подсчитанных владельцем ортогональных изгибов **49**, исходных сегментов **91**, электрических Net **15**.

`validate_circuit=0 errors` не снимает ни одной из этих проблем. Отчёт с полной геометрией имеет `checked_symbol_geometry=true` и `checked_measured_text=true`, но **valid=false**.

## 4. Тестирование

[Github Actions v4 run 43608095630](https://github.com/Tridgi/gost-schematic/actions/runs/43608095630), оба задания Python **3.12** и **3.13** выполнили модельный gate; [pytest 3.12](tl494_v4/evidence_runs/43608095630-1/pytest_3.12.txt): **13 passed**; [Ruff 3.12](tl494_v4/evidence_runs/43608095630-1/ruff_3.12.txt): **All checks passed**. [Audit output](tl494_v4/evidence_runs/43608095630-1/audit_3.12.txt): `TEST=0 RUFF=0 AUDIT=0`. Тесты включают физический FB INPUT, 23/15, выбор УГО, 1 µm/2.99 mm/3.00 mm, X и явные foreign-Net dots. Это **не** все тесты репозитория и **не** утверждение полной GOST-соответствия.

## 5. AFTER — ЗАБЛОКИРОВАН, не подменён ручным SVG

Не изготовлены новый «чистый» полный SVG/PNG и PDF: это было бы преждевременным после **9 геометрических ошибок** и до принятия полноценного глобального многовыводного маршрутизатора. Нельзя искусственно исправить старый SVG, подтолкнуть подписи или масштабировать УГО ради красивого превью. На текущем этапе есть `AFTER` только для **типизированной модели и диагностик**, не для печатного листа.

- **Issue #108 owner ELEKTRIK NET**: глобальный многовыводной router, genuine wire ↔ symbol/text DRC с 3/2/1 мм, распутывание 32 X, A3/print arrangement. Текущий owner planner по фактическому исходному коду поддерживает только **preview для пары физических PinRef**, а не 23/15 industrial route. [Передано в #108](https://github.com/Tridgi/gost-schematic/issues/108).
- **Issue #109**: отдельные GND/Common/PE/Chassis typed view markers, без фиктивных физических pin/net. [Передано в #109](https://github.com/Tridgi/gost-schematic/issues/109).
- **Issue #110**: полноценный bottom→top PWM PAINT + 8 D4 and source pin models. [Передано в #110](https://github.com/Tridgi/gost-schematic/issues/110).
- **Issue #107/YGO/ESKD**: точная форма Шоттки (асимметричная по ГОСТ 2.730-73 таблица 5 поз.9) и MOSFET/конденсаторы/магнитопроводы остаются **DRAFT** до независимого QA и сопоставления с пользовательским оригиналом; [YGO2 PR #113](https://github.com/Tridgi/gost-schematic/pull/113), [ESKD PR #112](https://github.com/Tridgi/gost-schematic/pull/112). Шрифты не передаются пользователю.

Снимки исходной схемы 640×290 и BOM 640×702 SHA-256 по отдельности зафиксированы в плане. Файлы пользователя доступны в контексте чата, но **не объявлены загруженными в GitHub**. Недостаточность независимого source pixel 1:1 подтверждения остаётся явным `BLOCKED`.

**Go/No-Go:** NO-GO на printable AFTER until full DRC valid, preserved 23/15/16 and owner ESKD/QA signoff. No merge, no forced SVG post-edit.

# QA #92 — независимый выпускной шлюз электронных Э3 Cycle 7

**Статус на 14.11.2026:** **PARTIAL PASS + BLOCKED FULL RELEASE**. Ни один УГО не APPROVED. QA не объединяла PR, не меняла `src/`, `main`, работу E1 Issue #83 и не приписывала абстрактным контактам паспорта изготовителя.

## 1. Точные версии и реальные исполняемые исходники

| Проверяемая область | Фиксированная версия реализации | Реальные байты |
|---|---|---|
| Интеграционная база | `integration/stage0-12` `578e018f2b0be37b37fa4c8e52692cc1c5f941c5` | настоящий пакет `gost_schematic` в pytest/Actions |
| ELEKTRIK #87, ИС DA/DD | ветка `parallel/electrical-ic-contract-cycle7`, **`0ea5bddbc0de658baefab2bdd8803576c41099ea`** | Реальный `IcDeviceDefinition` + `IcSymbolSpec` + `ic_serde`; только synthetic 2/4/8/14/40/64, нет vendor pinout |
| PAINT #88 | ветка `parallel/rendering-ic-cycle7` **`f8f9dc4c1fd8266b807dea9d6f268d971bec8d7a`** | `src/.../ic_rectangular.py` blob **`a2077cd21bcd5f497ac3304bf7f9d0d76d6b32bd`**; точная копия `.txt` в тесте с выполнением функций оригинала |
| YGO 2 #89 | ветка `parallel/catalog-electronic-cycle7` **`ddb7881c52055fe44120a36015a469a847c70c16`** | неизменённые первые 6 реальных catalog JSON blobs, физические паспорта и символы |
| ELEKTRIK #90, продолжения | ветка `parallel/electrical-netrefs-cycle7`, **`0738059d8d4c0f5b8854a73018501fb16543434b`** | Реальный `NetContinuationProject`, `validate_net_continuations`, строгий `netrefs_serde`, 2 реальных фрагмента CTRL; совместные 1:1 схемные шрифты ещё BLOCKED |
| ESKD #91 | ветка `parallel/standards-electronic-cycle7` **`9aa2d98a22a8dc8bac0394e744d205dcc336ecff`** | `docs/standards/issue-91-cycle7-electronics-cards.json` blob **`4f31d9e24cb097c6c9e38263c0bea1d793acaae7`**; 2 исходных сравнительных SVG также pinned |

Снимки новых исходников проверяются реальной формулой Git blob SHA1 и сохраняются под `tests/fixtures/qa_cycle7_*`; оригинальный Python #88 исполняется через `SourceFileLoader` **как настоящий код без заменённых функций, без моков, без изменений `src/`**. Все источники reproducible offline в `pytest`. `tests/qa_cycle7_support.py` — только загрузчик и контроль SHA. Для ESKD тест строго подтверждает только корректность *описания источника/статуса*, не графическую подпись по ГОСТ.

## 2. Независимая матрица (PASS / FAIL / BLOCKED)

| QA-ID | Критерий | Статус и доказательство |
|---|---|---|
| E92-IC01 | Э3 ИС 2/8/14/40/64, отдельные физические номера/имена/строки | **PASS renderer-only**: код PAINT #88 действительно выводит 2/8/14/40/64 независимых тестовых контактов. **PARTIAL PASS real IC #87**: теперь есть типизированный пакет DA/DD, `PinRef`, split-unit и строгий JSON; **BLOCKED manufacturer**: номера **синтетические**, нет паспорта конкретной марки/корпуса и доказанной межкомандной совместимости всех 64 точек |
| E92-IC02 | Реальная OpenGost Type A ink + 300DPI | **PASS**: внешний SIL OFL OpenGost Type A SHA256 `f77d96f832b7c902d42fc391fddf15b622c1eadeb263dd31b926888d72e0773a`, h=2500µм; для каждой реально нарисованной строки тёмные пиксели находятся внутри её самостоятельного glyph ink box. Не делался вывод об APPROVED |
| E92-IC03 | Положение портов/номеров, разные стороны, поля | **PASS для синтетической графики**: реальные SVG `ic-physical-pin-leads`, `data-pin-number`, координаты **внешнего** разрешённого контакта сверяются с `x2/y2` линий; отдельные основные и боковые поля. Проверяются 1/10/40 номера, текстовые узлы, отсутствие обрезки |
| E92-IC04 | Авто габариты, длинные русские/английские строки, невозможное размещение | **PASS test-only**: размер по настоящим глифам, шаг ряда и поле увеличиваются на модульной сетке; 1 µм смещение вывода вызывает `IC_PIN_ANCHOR_MISMATCH`, слишком маленькая страница вызывает `IC_PAGE_OVERFLOW`, дубли номера и узла — hard fail, некорректная подпись не отрезается |
| E92-POT | `resistor.variable`, `resistor.trimmer` | **PASS DRAFT first batch**: каждая — ровно три реальные `GraphicPin` и `PhysicalPin` 1/2/3 с отдельным W, стрелочный графический движок не участвует в постороннем проводящем штрихе. Независимые группы `(('1',),('2',),('3',))`, восемь D4, реальные SVG/PNG. **BLOCKED real part numbering**: номера абстрактны |
| E92-FU | `fuse.general` | **PASS DRAFT geometry/topology**: 2 контакта, две токопроводящие группы, внутренний графический штрих не замыкает Circuit.Net. **BLOCKED normative 1:1** до ESKD/MAIN2 |
| E92-BJT | NPN, PNP, C/B/E, стрелки, корпус | **BLOCKED**: в ветке #89 ещё нет реальных пар УГО+PhysicalPin; нельзя признать без кода |
| E92-MOS | N/P MOSFET, G/D/S/B, графический корпус | **BLOCKED**: нет реальных пар и доказательства гальванической изоляции/пакета |
| E92-VD | Schottky, LED, photo, varicap | **BLOCKED**: нет новых исполняемых пар; старые general/zener НЕ доказывают новых разновидностей |
| E92-XP | реальные XP/XS | **BLOCKED**: нет физической модели разъёма; запрещено имитировать порт сетевой стрелкой |
| E92-NET | Два визуально разорванных фрагмента одной `Net` | **PASS baseline semantic only**: настоящий `Circuit.Net` хранит оба `PinRef` без проводника, Circuit validation действительно принимает. **PARTIAL PASS #90**: теперь имеются реальные маркеры, два листа, адреса, пары и roundtrip; **BLOCKED** общий production-маршрутизатор и замер OpenGost на листах |
| E92-NET-NEG | одинаковое видимое имя двух разных `Net` | **PASS baseline rejection**: `validate_circuit` возвращает `DUPLICATE_NET_NAME`. **PASS реальные отрицательные регрессии #98**: `E3_CONT_SHEET_UNKNOWN`, `E3_CONT_ADDRESS_MISMATCH`, `E3_CONT_DUPLICATE_ENDPOINT_ID`, `E3_CONT_STUB_WRONG_NET`, `E3_CONT_LABEL_AMBIGUOUS` проверяются на исходном Python (включая два Net с одинаковой видимой подписью) |
| E92-MIX | единый E3 образец DA/DD, 2 транзистора, 3 диода, FU, R, XP, 2 continuation | **BLOCKED**: полноценные BJT/MOSFET/VD/XP отсутствуют, а физический IC пока synthetic. Нельзя выдавать составленную из фиктивных компонентов демонстрацию за настоящий E3. Собраны только воспроизводимые частные галереи |
| E92-ESKD | источники, корректность DRAFT статуса | **PASS metadata-only**: **107** нормативных карточек #91 имеют `normative_rule_status=PASS`, но **107 из 107** имеют `acceptance=BLOCKED`, `approval=DRAFT`. Уже существовавшие 12 карточек #27 лишь процитированы, не превращены в 107 новых готовых УГО |
| E92-REG | Базовая схема 16 проводов и старый каталог | **PASS**: полные обычные тесты integration проходят; динамический `audit_catalog` сверяет число записей с реальными JSON и физическими паспортами, без захардкоженного конечного числа УГО |

**Определение PASS:** проверенная ограниченная функция действительно исполнилась с точными байтами owner-кода, а не присутствует только в заглушке JSON. **BLOCKED** означает отсутствие проверяемого кода/фактического паспорта или независимой нормативной подписи; это не скрытый `xfail`. **Ни один blocked критерий не считается сданным.**

## 3. Независимые отрицательные регрессии

- **Типизация физического устройства:** одинаковый номер/ID/координата/ряд отклоняются `IC_DUPLICATE_*`; нулевая строка, неверный pin role, NC/IN/OUT-семантика не заменяются домыслом.
- **Геометрия PAINT:** смещение настоящего внешнего контакта на 1µм должно отклоняться `IC_PIN_ANCHOR_MISMATCH`. Слишком маленькие лист/тело и текст не обрезаются, `IC_PAGE_OVERFLOW`/ `IC_TEXT_OVERFLOW`; высота шрифта Type A не уменьшается ради помещения.
- **Дискретные УГО:** вторичный вывод не исчезает, три физических номера сохраняются при всех восьми ориентациях, неизвестный физический номер возвращает `UNKNOWN_PIN`/ `PIN_MAPPING_MISMATCH`, фиктивное внутреннее проводящее перемыкание не должно проходить `inspect_conductor_topology()`.
- **Circuit.Net:** два независимых Net с одинаковым именем дают `DUPLICATE_NET_NAME`; физическая схема с неверным PinRef отклоняется; картинка не является источником истинности сети.
- **ESKD:** карточки должны различать `normative_rule_status=PASS` и `acceptance=BLOCKED`. Жёсткие guards № F91-IC-NUMBERS, F91-FUSE-TABLE, F91-NPN-SCREEN, F91-CHAR-LIMIT, F91-PLUG-OFFPAGE не позволяют присвоить APPROVED на основании рисунка.

## 4. Реальные изображения и измерения

В `.github/workflows/qa-cycle7-visual.yml` загружается настоящий OpenGost Type A v0.7 **в runner**, SHA-256 проверяется заранее, бинарные шрифты в PR/отчёты не попадают. Запуск:
- Вызов точного исходного Python PAINT `render_resolved_ic` для 2/8/14/40/64 тестовых контактов, SVG с индивидуальной записью текста и реальных концов линий, PNG 300 DPI посредством CairoSVG; для **каждого** текстового ink-box проверены реальные тёмные пиксели из PNG, а не один лишь manifest.
- Вызов установленных `parse_symbol`, `parse_part`, `render_symbol_svg` с точными YGO JSON для 3 первых DRAFT УГО; по 2 реальных SVG+PNG на символ, пиксели не нулевые, overlay реальные порты, conductor islands независимы.
- Отчёты `qa-cycle7-ic-evidence.json`, `qa-cycle7-discrete-gallery.json` содержат SHA-256 каждой SVG/PNG, номера и координаты, размер px, TrueType fingerprint, модель ограничений. Ни один артефакт не называется полным mixed E3.

**Пример успешно отработавшего исходного этапа:** [Actions #43522428480](https://github.com/Tridgi/gost-schematic/actions/runs/43522428480), [PNG/SVG/JSON artifact #14083271894](https://github.com/Tridgi/gost-schematic/actions/runs/43522428480/artifacts/14083271894) — это **старый** PAINT SHA, после него source P0 anchor semantics исправлены. **Актуальный** тест PAINT **`1b09e59`** имеет собственный успешный [Actions #43523095777](https://github.com/Tridgi/gost-schematic/actions/runs/43523095777) (вариант с внешним электрическим концом); следует использовать последний успешный прогон на точном QA HEAD.

## 5. Нормативные ограничения и готовность к выпуску

ESKD #91 подтвердил нормативные **кандидаты**, не готовые графические устройства. Для физической ИС нужны проверенный datasheet+revision+package, тождество всех физических выводов, отсутствие скрытых NC/power, корректная связь split-unit package; для BJT/VD/FU/XP нужны конкретные table/position и внешние 1:1 фотографии/печатные масштабы. Никакое содержимое `tests/fixtures/qa_cycle7_*` не является регистрацией УГО в production каталоге.

**Обновление HEAD во время независимого аудита:** теперь созданы Draft PR #97 и #98 на `IcDeviceDefinition` и `NetContinuationProject`; выполненные до появления этих PR BLOCKED-строки исторические, требуют новых исполняемых QA-регрессий по точным SHA. **Release decision: NO-GO полного E3 Cycle 7.** Допустима ограниченная техническая приёмка DRAFT PAINT, трёх YGO символов и изолированной семантики ELEKTRIK #87/#90 после исправления ошибки XML #98. Требуется следующий набор #89, реальный manufacturer pinout, контрактная интеграция #87↔#88, независимый source-backed ESKD-1:1 signoff. QA PR держать Draft и не объединять с E1 #83.

## 6. CI / архитектурная изоляция

`ruff check .` / `pytest -q` на 3.12 и 3.13; `scripts/audit_symbol_catalog.py` проверяет динамическое число УГО; `scripts/verify_wheel_payload.py` валидирует реальные JSON в wheel. Дополнительно отдельный Actions поднимает точную TypeA и PNG. Выполнение не зависит от `git fetch/show` во время pytest, файлы owner-веток исполняются из SHA-проверенных тестовых копий. PR должен быть создан строго из `parallel/qa-electronic-cycle7` в `integration/stage0-12` как **Draft**, только после завершения воспроизводимой проверки. Отдельная E1 Issue #83 и production-ветки исполнителей не редактировались.

## 7. Последующий независимый реальный аудит PR #97 / PR #98

После первоначальных блокировок владельцы подготовили **реальные Draft PR #97** (`0ea5bddbc0de658baefab2bdd8803576c41099ea`) и **#98** (`0738059d8d4c0f5b8854a73018501fb16543434b`). QA не использует устаревшее предположение об отсутствии классов. `tests/qa_cycle7_electrical_sources.py` фиксирует точные Git blob SHA, временно загружает владельческие `ic.py`, `ic_serde.py`, `netrefs.py`, `netrefs_serde.py` и **настоящие примеры владельцев**, без подмены production-моделей. 

**PASS на собственном реальном owner-коде:** 12 synthetic analog/digital корпусов (2/4/8/14/40/64) с настоящими типизированными `IcPhysicalPin`, отдельными `IcUnit`, единственным физическим `DA1`/`DD1`, `PinRef`, уникальными координатами и lossless JSON. Отрицательные тесты: повтор физического номера, исчезновение non-NC pin, неправильный view unit, физический `NC` под Net → `IC_NC_CONNECTED`, несоответствие внешнего якоря; 8 поворотов/отражений сохраняют идентичности. **Ограничение:** примеры явно `TEST_IC_*`, **не** datasheet/реальный корпус.

**PASS частично по #98:** 2 реальных разнесённых видимых локальных проводника на двух листах, одна предсуществующая `Circuit.Net` `CTRL` с точными `DD1.5` и `VT1.G`, два явных `M-OUT/M-IN`, адреса `1/D4↔2/B7`, строгая `netrefs_to_json/from_json` с обязательным внешним `Circuit`. Независимые отрицательные тесты на чужой лист/адрес, дубли ID, чужую сеть, неверный физический PinRef и совпадающую подпись на **разных** Net (`E3_CONT_LABEL_AMBIGUOUS`). PNG/SVG и 12 валидных synthetic IC JSON с контрольными SHA собирает `scripts/qa_cycle7_electrical_visual.py`. **Ограничение:** штрихи и подписи двухлистового SVG пока без измеренной высоты OpenGost ink.

**ИСТОРИЧЕСКИЙ FAIL P0 (исправлен владельцем в текущем #98):** `sheet_svg()` одновременно задаёт namespaced тег `{http://www.w3.org/2000/svg}svg` и атрибут `xmlns` вручную. При `ET.register_namespace("", "http://www.w3.org/2000/svg")` (вызывается общим рендерером в другом тесте/пакете) получается **дублированный `xmlns`**. `ET.fromstring` закономерно выдаёт `ParseError: duplicate attribute: line 1, column 40`. Это дефект **порядка импортов**, а не семантического графа: отдельный чистый запуск PNG может быть зелёным, тогда как полный совместный Python процесс выдаёт нечитаемый SVG. Независимый регрессионный тест **сохранён обычным обязательным тестом**, без `xfail`/skip; текущее состояние исправления рассматривается в разделе 8. Сообщено в [Issue #90](https://github.com/Tridgi/gost-schematic/issues/90#issuecomment-6867264493). Техническое доказательство: [QA CI #43525050784](https://github.com/Tridgi/gost-schematic/actions/runs/43525050784), **1917 passed / 1 failed**; исторический прогон; нельзя переносить его результат на исправленный SHA.

**ESKD #91:** первоначальный source comparison SVG имел некорректный XML; исправлен владельцем в HEAD `4445b9d916217756d2586e4257a2b59ad72f9103` (новый SVG blob `67b94ce65de9b79aab45381a9a0d4aafb37a4ffc`). QA проверяет исправленное изображение XML-парсером. Нормативные `107 source-rule PASS` / `107 approval BLOCKED` не изменены.

**Историческое решение на прежнем SHA `cd004f626450367082a44784cac7f9563dbe9eef`:** NO-GO общего двухлистового SVG. На актуальном SHA `0738059d8d4c0f5b8854a73018501fb16543434b` этот конкретный XML-дефект исправлен (см. раздел 8); полный сквозной E3 остаётся NO-GO по другим причинам. Это точный, намеренно красный gate с подтверждёнными PASS/FAIL/BLOCKED, а не тест, отключённый ради зеленого CI.

## 8. Повторный аудит исправления SVG owner #98

**Ранее FAIL (исходный HEAD `cd004f626...`):** в `sheet_svg` возникал повтор `xmlns` при глобальном `ET.register_namespace`. Это было подтверждено независимым реальным `pytest` без xfail на 3.12 и 3.13.

**НОВЫЙ точный HEAD владельца `0738059d8d4c0f5b8854a73018501fb16543434b`** устранил повтор `xmlns`, вызывает `ET.register_namespace("", SVG_NS)`, задаёт namespaced SVG root **без** вручную дублированного `xmlns`. QA перепривязала fixture к точному Git blob **`21e76f0ab779cbc13eeeffdd1e0273fa38869e8f`** и сохранила **тот же strict тест** с предварительной регистрацией namespace, не отключая его. Это полноценная регрессия на предыдущий дефект; новый статус PASS должен подтверждаться **последним полным CI именно на перепривязанном QA HEAD**. Не интерпретировать старую красную CI #43525050784 как дефект нового #98.


## 9. QA 2 — актуализация исходников и интеграционный gate (14.11.2026)

Актуальный ELEKTRIK IC PR #97: `0ea5bddbc0de658baefab2bdd8803576c41099ea`, реальный Git blob `ic.py` `cd93b1f993a53d684d4830c2cee77126e96b06ce`. QA fixture заменён байт-в-байт; независимая функция `verified()` продолжает проверять Git blob SHA-1, а регрессии NC/split проверяют именно новую реализацию `IC_UNSAFE_LEGACY_ADAPTER`. ELEKTRIK netrefs PR #98: `0738059d8d4c0f5b8854a73018501fb16543434b`; blob `netrefs.py` `a8c13dba69479e31ed02c91567b564f860b5d5f6`; owner demo blob `21e76f0ab779cbc13eeeffdd1e0273fa38869e8f`. Ошибка namespace проверяется без xfail.

### Межкомандная совместимость — точный объём доказательств

| Взаимодействие | Статус | Ограничение |
|---|---|---|
| #97 typed physical `PinRef` → #93 `ResolvedIcPin.anchor`, простая synthetic 2-pin | **PASS (test-only handoff)** | Оба реальных исходника выполняются вместе, координаты не меняются; перевод роли явный и существует только в QA |
| #97 ↔ #93 полный 8/14/40/64 с Type A и D4 | **BLOCKED** | Нет принятого production-адаптера, который согласует измеренный PAINT размер, `visual_row`, абсолютный anchor и все электрические роли без потерь |
| #97 split/NC → прежний `PartDefinition` | **PASS (expected hard rejection)** | Актуальный `to_legacy_part` отвергает NC и multi-unit; обходить это запрещено |
| #96 ProjectService ↔ #97 IcDeviceDefinition/split `PinRef` | **BLOCKED** | #96 сохраняет legacy `PartDefinition`/`SymbolDefinition` из установленного каталога; отсутствует типизированная сериализация `IcDeviceDefinition`, единый package ID и многие-to-one mapping unit→physical component |
| #96 standalone E3 проект (6 интегрированных компонентов, 16 проводов, 3 узла) | **PASS owner-CI only** | Доказано на собственной ветке #96, но это не интеграционный тест с новыми IC/discrete/netrefs |
| #98 logical `Circuit.Net` + 2 continuation + SVG XML | **PASS ограниченно** | Только реальный пример 2 листов, имена/адреса и строгий XML; нет общего layer/router и измеренного Type A для всех листов |
| #94 потенциометр / trimmer / FU | **PASS DRAFT gallery** | Только три новые пары; не подтверждает BJT/MOSFET/Schottky/XP/XS |
| #95 нормативные 107 карточек | **PASS provenance, BLOCKED symbol approval** | Нулевое число APPROVED; внешняя ручная проверка 1:1 остаётся обязательной |

**Решение QA 2:** все текущие PR #93–98 допускаются максимум к *ограниченному рассмотрению DRAFT отдельных модулей*. Ни один не обосновывает утверждение о готовности сквозного E3 проекта с физическими многочастными ИС; **NO-GO полного Cycle 7**. Перед технической интеграцией #97↔#93↔#96 требуется отдельный executable end-to-end контрактный тест с холодным reopen и проверкой каждого `PinRef`, а не только успешные CI на отдельных ветках.


## 11. QA 2 — независимый повторный аудит 15 УГО, портретной ИС и P1.1 (14.11.2026)

**Release mode:** все исходники владельцев берутся из неизменяемых Git-коммитов отдельными checkout в GitHub Actions; только временный runner получает оригинальные Python/JSON. QA #99 изменяет исключительно собственные \`scripts/\`, \`tests/\`, \`.github/workflows/\` и \`docs/qa/\`; ни одного файла \`src/\` не коммитит. MAIN/integration не объединялись. Старые 31 QA-файла не заменялись.

### 11.1. Зафиксированные owner-код и Git blob SHA-1

| Владелец | HEAD проверяемого исходника | Git blob исходника |
|---|---|---|
| PAINT PR #93 | \`165017630dc911c3006eda35424d8293498db100\` | \`rendering/ic_rectangular.py\` \`bff0caf982a14ebd2bacda15b419f9b4bcc16f70\` |
| ELEKTRIK IC PR #97 | \`16e689dfe3ad4b4a9dd17974f4d4f9b8f30c86fa\` | \`electrical/ic.py\` \`879ced36cd11c2607bcac1db345bd75cae06e54a\`; \`ic_paint_bridge.py\` \`edf70d41f2833f8a9504d20632398eb8294ad2ea\` |
| ELEKTRIK NET PR #98 | \`8ab0778a67c2e56be4be9cd0297e454413f56028\` | \`electrical/netrefs.py\` \`729a53b4ea19d68b0be1372e745863a11eb83d07\` |
| YGO PR #94 | \`37f7c5e58938db1d5bcf308ff04e740356afc0e4\` | \`docs/catalog/electronic-cycle7-second-batch-cards.json\` \`19e0b0ad1c8d88819bf8a6e46511c386b30f7899\`, \`issue89-acceptance-matrix.json\` \`0c16ba218f64437aa202ec56a7e30b02fdc73866\` |
| MCP PR #96 | \`a58ecd388a7cf99fe6cc2f7340d39403b0fa9abf\` | \`agent_project/service.py\` \`6d20a3020e30c114d9e9931e5e4762b1c3cb9489\` |
| ESKD #95 (MERGED) | \`1e54166304928ba27eaf674d79597e1d527fb3bb\` | \`issue-91-deep-source-audit.json\` \`07b2ab53b64fe40fe35750f0a21b52db8ca66c30\` |

Более новые PR HEAD \`#97 20bd39c794bc375937fe332c173e17955554d1e1\` и \`#96 71168e303635eaab4607e4f3ebe2c3458a523135\` на момент проверки изменили **только документацию, тесты или workflow**, но не указанные проверяемые файлы production. Не переносить результаты на будущие изменения исполняемых исходников без нового Git blob и нового QA CI.

### 11.2. Все 15 реальных SymbolDefinition / PartDefinition

**Независимый результат: PASS DRAFT для физических моделей и SVG/PNG** (не нормативное APPROVED). Скрипт \`scripts/qa_cycle7_live_source_gate.py\` в обоих Python действительно вызывает владельческие \`load_symbol\`, \`load_part\`, \`validate_circuit\`, \`inspect_conductor_topology\`, \`render_symbol_svg\`; 15 пар, 30 отдельных изображений (clean/diagnostic) с действительным CairoSVG 300 DPI, контрольными SHA-256 и ненулевым количеством тёмных пикселей. Для каждого УГО — D4 (0/90/180/270 × зеркало), уникальные \`PinRef\`, независимые островки меди и отрицательное тестовое «фиктивное замыкание» (hard rejection).

| ID | Реальные физические роли | Источник ESKD (кандидат) | QA DRAFT |
|---|---|---|---|
| \`resistor.variable\` | 1=A, 2=B, 3=W | ГОСТ 2.728-74 табл.1/4, табл.6/3 | PASS |
| \`resistor.trimmer\` | 1=A, 2=B, 3=W | ГОСТ 2.728-74 табл.1/9, табл.6/5 | PASS |
| \`fuse.general\` | 1=A, 2=B | ГОСТ 2.727-68 §4 табл.3/2 | PASS |
| \`transistor.bjt_pnp\` | 1=B,2=C,3=E | ГОСТ 2.730-73 §8 табл.7/1а | PASS |
| \`transistor.bjt_pnp.with_case\` | 1=B,2=C,3=E; корпус НЕ электрод | ГОСТ 2.730-73 §8 табл.7/1а + примечание | PASS |
| \`transistor.bjt_npn\` | 1=B,2=C,3=E | ГОСТ 2.730-73 табл.1/2 и §8; **EXPERIMENTAL_DERIVED**, НЕ ошибочная табл.7/1б с экраном | PASS модели; source-1:1 BLOCKED |
| \`transistor.bjt_npn.with_case\` | 1=B,2=C,3=E; корпус НЕ электрод | тот же экспериментальный вывод | PASS модели; source-1:1 BLOCKED |
| \`transistor.mosfet_n_enh\` | 1=G,2=D,3=S; G изолирован | ГОСТ 2.730-73 §9 табл.8/3б | PASS |
| \`transistor.mosfet_n_enh.with_case\` | 1=G,2=D,3=S; контур НЕ вывод | §9 табл.8/3б + корпус | PASS |
| \`transistor.mosfet_p_enh\` | 1=G,2=D,3=S; G изолирован | ГОСТ 2.730-73 §9 табл.8/3а | PASS |
| \`transistor.mosfet_p_enh.with_case\` | 1=G,2=D,3=S; контур НЕ вывод | §9 табл.8/3а + корпус | PASS |
| \`diode.schottky\` | 1=A,2=K | ГОСТ 2.730-73 §6 табл.5/9 | PASS |
| \`diode.led\` | 1=A,2=K; фото-стрелки НЕ проводники | ГОСТ 2.730-73 §6 табл.5/10 | PASS |
| \`diode.photodiode\` | 1=A,2=K; фото-стрелки НЕ проводники | ГОСТ 2.730-73 §10 табл.9/2 | PASS |
| \`diode.varicap\` | 1=A,2=K; промежуток обкладки не замыкает контакт | ГОСТ 2.730-73 §6 табл.5/6 | PASS |

Все реальные ID и классы физически присутствуют в PR #94. Но числа 1/2/3 пока абстрактны; реальные manufacturer package/datasheet/part-number pinout и независимые измеренные 1:1 наложения нормативных фигуры отсутствуют. Новая матрица #89 помечает *все 15* \`DRAFT_NOT_APPROVED\` и \`BLOCKED_NO_INDEPENDENT_1TO1_CALIBRATION\`. Физические XP/XS отсутствуют и не заменяются стрелкой именной цепи. **Ни одному УГО не присваивать APPROVED.**

### 11.3. PAINT + ELEKTRIK IC, портретная функция

**P1 BLOCKED**, потому что требование пользователя касается именно *неизменного корпуса и электрических идентичностей* при переключении \`PWM_CONTROLLER\`/кириллицы 90°↔0° для 8/14/40/64 и всех D4.

- Новый PAINT имеет экспериментальный \`IcTypographyProfile.PORTRAIT_FUNCTION_V2_DRAFT\`; в нём центральная функция по умолчанию может быть вертикальной. Глобальный legacy-профиль остаётся горизонтальным.
- Реальный ELEKTRIK #97 предоставляет \`IcTextAngle\`, \`revise_ic_text_orientation\`, \`propose_ic_paint_binding\` и \`bind_ic_paint_text_only\`; физический \`PinRef\` не должен зависеть от графического текста.
- Независимый настоящий OpenGost Type A инк-проход выявил воспроизводимый \`IC_TEXT_OVERFLOW: main.0 function text='PWM_CONTROLLER'\` при переключении на 0° внутри того же корпуса на D4 90° и 270° (включая зеркальные позы), на Python 3.12/3.13. Никаких pin relocation, font shrink, xfail/skip или замены fake-renderer. Отказ является правильным для переполнения, но означает, что **вся запрошенная матрица переключения ещё не принята**. Обязательные негативные тесты 1 μm якоря, страницы, препятствия/штрихов и измеренных глифов включены в live gate.
- Взаимозависимые TOP/BOTTOM тесты — **не** подтверждение независимого поворота одной функции; называть их заменой запрещено.
- Эталонный manufacturer pinout, сквозное \`IcDeviceDefinition\` через ProjectService, Type A 1:1 ESKD, реальные PWM-устройства остаются BLOCKED.

### 11.4. Реальные именованные цепи PR #98

**PASS семантики и XML**: двухлистовая схема имеет строго одну заранее объявленную \`Circuit.Net\` \`CTRL\`. Трёхлистовая новая схема содержит **три** реальные \`Circuit.Net\`: \`CTRL\`, \`REF\`, \`ENABLE\`; запрещено требовать одну для обоих образцов. Проверены пары маркеров, \`PinRef\` inventory, адреса (лист/зона и адрес элемента), сериализация и восстановление с оригинальным Circuit, три зарегистрированных SVG namespace и отсутствие «дорисованной» физической цепи, реальное Type A и 300-DPI SVG/PNG. Негативный пример чужого \`net_id\` должен отказать. Полная нормативная 1:1 форма маркера ещё BLOCKED, физические XP/XS нельзя подменять continuation.

### 11.5. MCP #96, сохранение/открытие

**PASS ограниченный автономный P1.1**: оригинальный \`Circuit\` содержит 6 компонентов, 5 Net, 16 сегментов и 3 явно объявленных узла; сохранённый SHA-проект открывается в новом процессе, который запрещает импорт исходного \`examples.*\`. Проверены SVG/PNG и запрет path traversal. **BLOCKED** на сериализацию/reopen новой многосекционной \`IcDeviceDefinition\` из #97; нет доказанной согласованности package/unit/NC/physical PinRef сквозь cold-open. Это не дефект проверенного старого шестикомпонентного примера.

### 11.6. Wheel, Ruff, CI и решение MAIN 2

Вторая независимая матрица для 36 доступных каталоговых УГО считает **21 статический символ JSON + 15 параметрических катушек**, а не 36 статических JSON. Проверяется wheel ZIP на наличие всех 21 SymbolDefinition JSON, 21 PartDefinition JSON и 15 winding definitions. Нельзя считать, что все 36 находятся в \`catalog/symbols/\`. Проведение source blob+wheel и matrix на Python 3.12/3.13 обязательно. Шрифты инсталлируются **только** в GitHub Actions, никогда не помещаются в артефакт.

**Решение:**

| PR | QA решение | Причина |
|---|---|---|
| #95 ESKD | MERGED (исторически завершён), \`APPROVED=0\` | нормативное исследование и 107 карточек, не готовые УГО |
| #94 YGO | **EXPERIMENTAL INTEGRATION возможна только как DRAFT** | 15 реально работающих пар, D4, отдельные контакты, images; не vendor/1:1 ГОСТ |
| #98 NET | **EXPERIMENTAL INTEGRATION возможна только как DRAFT** | реальные 2/3 листа и Net identity, строгий SVG/XML; не физические XP/XS |
| #96 MCP | **EXPERIMENTAL INTEGRATION только P1.1 standalone/read-only** | 6-part cold-open работоспособен; multi-unit IC persistence — HOLD |
| #93 PAINT | **HOLD для пользовательского portrait 90°↔0° default** | нет полной зелёной матрицы неизменного корпуса для длинных слов/D4; старый renderer-only — отдельный PASS |
| #97 ELEKTRIK IC | **HOLD для полной межветочной интеграции** | typed split PinRef и новый text binding экспериментальны; нет полного общего P1 и persistence |
| #99 QA | **HOLD / KEEP DRAFT** | независимый mandatory P1 продолжает обнаруживать неудовлетворённые случаи; не выключать gate ради зелёного CI |

Актуальные Actions и artifact ZIP должны быть привязаны в PR #99 к exact QA HEAD, а не к историческим коммитам. **Проверка завершения Cycle 7: NO-GO.**

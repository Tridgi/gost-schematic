# ESKD Cycle 12 — независимая приёмка реального NEW-route TL494 (DRAFT / NO-GO)

**Задание:** [MAIN 3 Cycle 12, PR #112](https://github.com/Tridgi/gost-schematic/pull/112#issuecomment-6892445975). Исходник исключительно `e695c415fdced164b0e0c39c5249d030795a0aa6`, неизменяем. [Нормативный пакет ESKD](./issue107-cycle10-real-paint-print-gate.md) остаётся действующим. Никакие УГО/детали не утверждены формально: **13/13 DRAFT, 0 APPROVED**.

## Реальная машина-источник: что сравнивается

- Замороженный типизированный первоисточник: `examples/tl494_model_output/TL494_full_typed_netlist.json`, **Git blob** `c4cfd515782bf856a7a44fbe2c2ceacd303208d6`. Данные: 23 реальных `elements`, 15 точных имён `nets`, поимённые 62 `PinRef`, 16 `DA1.1..DA1.16`. `routed=false`, `rendered_full_e3=false`. Ровно один и тот же файл `git show` из frozen commit проверяется по `git hash-object` без ручного обновления.
- Первая реальная попытка новой трассировки: [NET #114 true A3 owner run #43654672504](https://github.com/Tridgi/gost-schematic/actions/runs/43654672504), архивы `owner-114-compact-A3-source-23net-3.12/3.13`. Этот archive **зафиксирован**, поэтому его точная owner router-версия `5c6feb90580ed846aa297c71d3c91afacfc3f0bc` **НЕ автоматически равна самому последнему HEAD** NET #114. Это положительный реальный источник для DRAFT-аудита, не dynamic current-head acceptance.
- Размещение в артефакте RECON #115: `e56397300875ac155a316a9bfebe2601358a4147`. Отдельные новые SVG `TL494-compact-A3-clean.svg` и `...diagnostic.svg`, реальные PNG 300 DPI и `TL494-compact-A3-route-drc.json`. Подлинные hash каждого SVG/PNG переносит JSON ESKD. Никакого подрисовывания SVG или ремонта Net.
- Новый скрипт [`scripts/eskd_cycle12_routed_source_gate.py`](../../scripts/eskd_cycle12_routed_source_gate.py) сам сопоставляет **каждую физическую пару Net/PinRef** с исходным frozen JSON, а не просто 15/62 totals или собственную ссылку владельца `source_net_diff=[]`. `tests/test_standards_cycle12_routed_source_gate.py` намеренно меняет две принадлежности PinRef между сетями с сохранением общих чисел и требует FAIL. Граница 3мм — **реальный просвет ink stroke**, не межосевая дистанция.

## Неподменяемые конкретные результаты настоящего архива

| Контроль | Фактический результат | ESKD-вердикт |
|---|---|---|
| Профиль 23/15/62, все DA1 физические 1…16 | Числа совпадают; 15 `net_members`, исходные 62 поимённых членства сверяются с frozen JSON | **PASS_SOURCE_TOPOLOGY** после сравнения |
| Имена 15 исходных сетей | `INPUT_POS→a_INPUT_PLUS`, `ENERGY_TRANSFER→TRANSFER`, `OUTPUT_NEG→b_NEGATIVE_OUTPUT` (три конкретные обратимые пары); исходный файл содержит длинные имена | **PASS_IDENTITIES_AFTER_TYPED_MAP**, но **BLOCKED_EXACT_NAME_PRINT_EXPORT**, если остаются краткие имена |
| Новый реальный `ExternalWireGraph` | **10/15** Net complete, **62** новых H/V сегмента, 15 новых junction, проводники длиной 2231,456 мм | **BLOCKED_INCOMPLETE**, не исторические 91 |
| Ещё не проведённые | `GATE_DRIVE`, `CONTROL_REFERENCE`, `FEEDBACK`, `OSCILLATOR_RT`, `COMMON`, владелец передаёт точные `ROUTE_NO_CLEAR_ORTHOGONAL_TREE_PATH` и `INK_VETO` | **FAIL_FULL_ROUTE** |
| `new_after_drc.error_count` | 0 по **проведённым 62 сегментам**, `after_erc_errors` указывает incomplete graph | **PASS_PARTIAL_DRC**, категорически **NOT PRINT_PASS** |
| 3мм между *соседними параллельными* различными Net | Скрипт независимо пересчитывает реальные `<line data-layer=wires>` с истинной шириной 0,3мм, при строго положительной общей проекции и без blanket X/T | **PASS_PARTIAL_ONLY**, полный лист **BLOCKED** |
| 2мм между отдельными УГО; 1мм между своими штрихами | Доказательства на **всех физических примитивах** после полной A3/A2 трассировки ещё нет. `new_after_drc.checked_symbol_geometry=true` само по себе не полноценное геометрическое доказательство | **BLOCKED_REAL_PRIMITIVE_INK** |
| Физический DA1 на SVG | 22 `<g data-layer=symbols>` + отдельная подлинная группа `<g data-owner=DA1 data-ink-source=real-native-PAINT-original-16leads>`, 16 настоящих физических pin-tip leads | **PASS_DRAFT**; 22 каталожных groups не означает потерю 23-й детали |
| Тип А / PWM | Настоящий hash OpenGOST `f77d96…` и `matrix(0 -1 1 0 …)` функция PWM снизу вверх в отдельной группе PAINT | **PASS_PROJECT_RENDER_PREF**, нормативное утверждение function-only rotation **BLOCKED** |
| Чистый/diagnostic PNG 300 DPI | Чистый монохромный; debug 16 зелёных квадратов в настоящих физических DA1 PinRef контактах, без зелёного на clean | **PASS_PROJECT_QA**, 300DPI не отдельное требование ГОСТ |
| Разрывные буквенные продолжения `b-X2/b-R5` | Точное исходное местоположение для новой A3 компоновки не подтверждено собственником #115; новые Nets/PinRefs вводить запрещено | **BLOCKED_SIGNED_COMPACT_REBIND** |
| Штамп, рамки, формат | Результат имеет `viewBox 5.55 6.1 402.6 244.052` при реальном `width=402.6mm`, `height=244.052mm`; сам owner отмечает 3 нарушения **редакционной 10мм-рамки**. Не выдавать за оформленный лист A3 ГОСТ 2.301/2.104 | **BLOCKED_PRINT_SHEET_RELEASE** |
| Фото источника: реальные номиналы/полярность, ориентация, 1:1 | Проверка только frozen typed Net, не pixel/photo crop; независимое сравнение с исходным изображением и полномасштабным нормативным чертежом отсутствует | **BLOCKED_USER_PHOTO_PARITY** |
| Замороженная старинная проводка | 91 исходный провод, 37 исходных точек, **9 DRC ERROR и 32 WARNING** | **EXPECTED_BAD_NEGATIVE**, не успешный результат |

### Источники и запреты смешения нормативного с редакторским

- ГОСТ 2.701-2008 §5.3.4 (способы выполнения схем): ≥1 мм соседние штрихи одного УГО, ≥2 мм отдельные УГО, ≥3 мм между соседними параллельными линиями соединения; 0,2–1мм допустимая толщина (0,3–0,4мм лишь рекомендация). Отделять **действительные границы штриха** от центровых осей; X/T не должны ложно получать глобальный трёхмиллиметровый запрет.
- ГОСТ 2.730-73: VD1 асимметричный катод Шоттки A/K сохраняется при D4, VT1 G/D/S из каталога. ГОСТ 2.728-74: C1/2/3/5/6 thin polarized(+), C4/7 fixed, R5 variable. ГОСТ 2.723-68: L1/L2 ferromagnetic **SOLID** core; ГОСТ 2.727-68 FU1. Точные PDF/table links, source-page anchors, статус DRAFT приведены в [Cycle9](./issue107-cycle9-independent-normative-audit.md), [Cycle10](./issue107-cycle10-real-paint-print-gate.md) и [22 source-cards](./issue107-ugo-normative-matrix.json).
- ГОСТ 2.721-74: Net `COMMON` — **сигнальная общая цепь**, не автоматическая защитная земля `PE`, chassis или физическое устройство заземления. ГОСТ 2.701 §5.5.3 против §5.5.4: не смешивать межлистовой безстрелочный `(лист,зона)` с одно-листовым допустимым стрелочным разрывом.
- Отдельный поворот **только текста функции** `PWM`, без всего УГО, не имеет полученного независимого стандартного первоисточника, поэтому **не APPROVED**; `FB`/`OC` и высота текста — представления редактора, подлежащие физической метрической проверке при финальном листе.

## Контракт для текущих владельцев

**NET #114:** необходимы все **15/15** с сохранением 62 физ. PinRef по оригинальным поименным Nets, `COMMON`, все пять конкретных `INK_VETO` устранены; трасса под реальные UGO/text keepout, не `0 errors` пустого графа. **RECON #115:** signed canonical `reference.tl494cn↔ti.tl494cn.pdip16` и `b-X2/b-R5` compact адреса, без подмены Net; **PAINT #93:** нативный SVG с полным 23/15 источником, clean/debug и PNG, никаких ручных поправок; **YGO #113:** фактические source 13 DRAFT UGO + primitive width/clearance; **IC #97:** все 16 физ. контактов, manufacturer roles, строгая симметрия typed model и renderer; **QA #99:** независимый photo/source 1:1 и проектные условия, не принимать частичный файл.

Для релиза 0.1 допустим **экспериментальный DRAFT engine с честными NO-GO дефектами**, но не «готовая ГОСТ-схема»: G2 (15/15 и полная DRC), G3 (актуальный полноценный артефакт), G4 (оригинал и нормативная проверка) **ещё BLOCKED**. Ветка #112 исключительно машинные нормативные проверки, документация, отрицательные тесты, никакого `src/` или слияния.

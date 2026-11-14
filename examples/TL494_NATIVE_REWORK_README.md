# TL494CN — нативное восстановление через GOST Schematic Engine (исследование)

**Вместо прежней вручную нарисованной схемы.** Это совершенно отдельная ветка, созданная от `integration/stage0-12`. Исходная экспериментальная ветка с самодельным SVG остаётся без изменений для истории, но её чертёж **не принят**.

## Реальный API
`examples/tl494_native_rework.py` выполняет:
- разрешение стандартных `PartDefinition`/`SymbolDefinition` через `CatalogResolver`;
- графические УГО `inductor.air_core`, `capacitor.electrolytic`, `transistor.mosfet_n_enh`, `diode.schottky`, `fuse.general`;
- создание `Circuit(ComponentInstance, Net, PinRef)`;
- получение координат **из** `ComponentInstance.pin_positions()`, сверку физических номеров и положения каждого контакта с ожидаемой геометрией;
- `ExternalWireGraph` с настоящими `WireSegment` и явными точками соединений;
- `validate_external_wires`, `validate_circuit`;
- **`inspect_type_a_font` + `PillowTextMeasurer`** со шрифтом `OpenGost Type A TT` (файл шрифта скачивается только в CI и в репозиторий не добавляется);
- штатный `render_external_wire_sheet`, который использует `layout_sheet` и `render_sheet_svg`.

### Никаких вручную нарисованных УГО в SVG
Отдельно изготовлены только экспериментальные **двухконтактные соединители X1/X2**, тоже через `SymbolDefinition`, поскольку утверждённая ветка соединителей PR #105 пока не слита.

## Что должно появиться после запуска CI

`examples/tl494_native_output/`:
- `TL494_native_power_clean.svg`;
- `TL494_native_power_diagnostic.svg`;
- `TL494_native_power_clean.png`;
- `TL494_native_power_diagnostic.png`;
- `TL494_native_power_manifest.json` с реальными диагностическими данными;
- `native_build_log.txt` с ошибками в случае неудачной сборки.

[Смотреть GitHub Actions workflow](../../.github/workflows/tl494-native-rework.yml).

## Границы результата
**11 компонентов силового каскада, а не полная схема.** DA1/TL494CN и обратная связь пока сознательно не включены. Нельзя утверждать, что создан полностью готовый `TL494_E3_clean.svg`. В полном контуре останутся:
- чтение и проверка реальных 16 выводов TL494;
- продолжения проводников `a` и `b` на исходном чертеже;
- правильные графические точки;
- все R1–R8, C3/C4/C7;
- принятие или изолированная проверка PAINT #93 и IC contract #97.

## Критерий успешного текущего шага
Прошёл сам **исполняемый проект GOST Schematic Engine** с реальным ГОСТ Тип А и сохранён SVG/PNG; имеется manifest. Если CI падает, следует сообщить об ошибке, а не подменять картинку ручным SVG.

**Нормативный статус:** DRAFT; УГО и оформление не утверждены как полный комплект ЕСКД.

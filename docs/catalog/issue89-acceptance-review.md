# YGO 3 — проверка 15 DRAFT УГО, Issue #89

Матрица: [`issue89-acceptance-matrix.json`](issue89-acceptance-matrix.json). Пакет ESKD: объединённый PR #95 / Issue #91. Дата 2026-11-14.

Это независимый **приёмочный шлюз**, а не сертификат ГОСТ. Названия и номера `1/2/3` в физических паспортах сейчас абстрактны; vendor pinout и подписанный геометрический overlay источника для всех 15 остаются **BLOCKED**.

Проверки: 15 отдельных `SymbolDefinition` и `PartDefinition`, роль/число/местоположение pin как конца токопроводящего штриха, 8 D4 поз, раздельные conductive islands, недопустимость подмены vendor pinmap, чистый SVG без псевдопортов, debug SVG, нулевое число APPROVED и полный динамический аудит.

## Протокол сравнения 1:1, который должен выполнить независимый ESKD/QA

1. Открыть **именно указанную позицию** ГОСТ (с учётом редакции/изменений). Скриншот PDF без шкалы ещё не доказывает размеры в миллиметрах.
2. Установить ориентацию оригинала и D4 CAD-образца. Сверить катод, отдельную пластину, полярность и стрелку эмиттера/канала, W контакты, штрихи плавкого FU и оптические лучи, не приписывая лучам/корпусу физический PinRef.
3. Сделать калиброванные source-crop, чистый SVG и 300DPI PNG; построить overlay 1:1 *только при известном масштабе/размерной опоре*, сохранить эталон/наложение/отклонения и решение независимого ревьюера.
4. При отсутствии калибровки решение `BLOCKED_NO_INDEPENDENT_1TO1_CALIBRATION`, а не PASS. При отсутствии производителя, package/revision и datasheet — отдельный `BLOCKED_NO_MFG_DATASHEET`.
5. Утвердить соответствующий тип только после ESKD+QA. Сейчас все 15 DRAFT; NPN без экрана — дополнительно EXPERIMENTAL_DERIVED: табл.7/1б в ГОСТ 2.730-73 содержит дополнительный внутренний экран.

## Ссылки на 15 отдельных эталонных позиций

| УГО | Источник | Исходный рисунок | Статус |
| --- | --- | --- | --- |
| `resistor.variable` | ГОСТ 2.728-74 табл. 1, поз. 4, PDF page=3 / printed page C.3; табл. 6 поз. 3 PDF page=20 | [PDF](https://helpeng.ru/public/normdoc/eskd/gost_2.728-74.pdf) | BLOCKED 1:1 |
| `resistor.trimmer` | ГОСТ 2.728-74 табл. 1 поз. 9 PDF page=6 / printed C.6; табл. 6 поз. 5 PDF page=20; distinction from table 1 position 10 dual variable plus trimmer | [PDF](https://helpeng.ru/public/normdoc/eskd/gost_2.728-74.pdf) | BLOCKED 1:1 |
| `fuse.general` | ГОСТ 2.727-68 §4, табл. 3 поз. 2 PDF page=3, May 2002 changes 1–2 | [PDF](https://www.nuvis.com.ua/GOST_2.727-68_ESKD.pdf) | BLOCKED 1:1 |
| `transistor.bjt_pnp` | ГОСТ 2.730-73, переиздание май 2002, изменения №1–4 §8 табл.7/1а (PNP); примечание о схематическом корпусе и зеркале | [PDF](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf) | BLOCKED 1:1 |
| `transistor.bjt_pnp.with_case` | ГОСТ 2.730-73, переиздание май 2002, изменения №1–4 §8 табл.7/1а (PNP); примечание о схематическом корпусе и зеркале | [PDF](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf) | BLOCKED 1:1 |
| `transistor.bjt_npn` | ГОСТ 2.730-73, переиздание май 2002, изменения №1–4 таблица 1/2 (N emitter) и §8 табл. 7/1а (PNP, базовая операция обращения стрелки); НЕ табл.7/1б | [PDF](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf) | BLOCKED 1:1 |
| `transistor.bjt_npn.with_case` | ГОСТ 2.730-73, переиздание май 2002, изменения №1–4 таблица 1/2 (N emitter) и §8 табл. 7/1а (PNP, базовая операция обращения стрелки); НЕ табл.7/1б | [PDF](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf) | BLOCKED 1:1 |
| `transistor.mosfet_n_enh` | ГОСТ 2.730-73, переиздание май 2002, изменения №1–4 §9 табл.8/3б (MOS N enrichment), примечание об изображении корпуса | [PDF](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf) | BLOCKED 1:1 |
| `transistor.mosfet_n_enh.with_case` | ГОСТ 2.730-73, переиздание май 2002, изменения №1–4 §9 табл.8/3б (MOS N enrichment), примечание об изображении корпуса | [PDF](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf) | BLOCKED 1:1 |
| `transistor.mosfet_p_enh` | ГОСТ 2.730-73, переиздание май 2002, изменения №1–4 §9 табл.8/3а (MOS P enrichment), примечание об изображении корпуса | [PDF](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf) | BLOCKED 1:1 |
| `transistor.mosfet_p_enh.with_case` | ГОСТ 2.730-73, переиздание май 2002, изменения №1–4 §9 табл.8/3а (MOS P enrichment), примечание об изображении корпуса | [PDF](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf) | BLOCKED 1:1 |
| `diode.schottky` | ГОСТ 2.730-73, переиздание май 2002, изменения №1–4 §6 табл.5/9 | [PDF](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf) | BLOCKED 1:1 |
| `diode.led` | ГОСТ 2.730-73, переиздание май 2002, изменения №1–4 §6 табл.5/10 | [PDF](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf) | BLOCKED 1:1 |
| `diode.photodiode` | ГОСТ 2.730-73, переиздание май 2002, изменения №1–4 §10 табл.9/2 | [PDF](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf) | BLOCKED 1:1 |
| `diode.varicap` | ГОСТ 2.730-73, переиздание май 2002, изменения №1–4 §6 табл.5/6 | [PDF](https://www.cad.dp.ua/gost/files/GOST2.730-73.pdf) | BLOCKED 1:1 |

## Реальные XP/XS

ГОСТ 2.755-87, таблицы 5/6, дают графические способы изображения вилки/розетки и контакта. Прежде чем добавлять физическую пару XP/XS, нужно выбрать подтверждённую форму, тип реального изделия/модель сопряжения, число и нумерацию контактов из документации. У N-контактного разъёма N отдельных `PhysicalPin`, каждый со своим `GraphicPin` и `PinRef`. Обозначение продолжения цепи по Issue #90 — **не** `PartDefinition` и **не** разъём. На этом этапе моделирование XP/XS **BLOCKED**; не добавлять фиктивные элементы для счётчика.

## Воспроизводимость

`ruff check tests/test_catalog_cycle7_acceptance.py`

`pytest -q tests/test_catalog_cycle7_acceptance.py`

Общая галерея всех 15, отдельные clean/diagnostic SVG и настоящий PNG 300DPI уже предусмотрены `examples/review_electronic_cycle7_extended.py` и `.github/workflows/catalog-cycle7-review.yml`. CI вместе с этой матрицей должен прилагаться к QA; 300DPI не означает 1:1 нормативное соответствие.

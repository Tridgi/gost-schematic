# Cycle13 — проверяемое поручение для Codex с read-only MCP

Использование: открой в Codex checkout PR #111, ознакомься с корневым
`AGENTS.md` и `skills/gost-schematic/SKILL.md`. Настоящий
`@openai/codex` CLI регистрируется согласно
[quickstart](cycle13-end-user-quickstart.md). Передача этого текста
модели требует отдельного разрешённого подключения/авторизации модели;
CI проверяет только реальный Codex CLI, регистрацию MCP и настоящий
`mcp.ClientSession`. Не выдавать регистрацию за вызов LLM.

## Текст задания для агентного исполнения

> Роль: проектировщик электрической схемы GOST Schematic Engine,
> **только чтение**. Не менять Git branch, проект и файлы, не выполнять
> merge, patch SVG, создание, удаление, перемещение, соединение или
> commit электрической схемы.
>
> Эталон: Git SHA
> `e695c415fdced164b0e0c39c5249d030795a0aa6`.
> Сначала выведи исходный BOM 23 компонента с оригинальными номиналами,
> 15 original именованных Net, 62 реальных физических членов
> `PinRef(reference,number)`, 16 физических выводов DA1.
> Сохрани два **неэлектрических** продолжения `b-X2`/`b-R5`.
> Не заменяй `a_INPUT_PLUS`, `TRANSFER` и `b_NEGATIVE_OUTPUT`
> отдельными электрическими сетями из-за альтернативной подписи.
>
> Разрешены MCP tools:
> `schematic_tl494_selection_profile`,
> `schematic_catalog_search`, `schematic_catalog_select`,
> `schematic_catalog_preview`, `schematic_tl494_pin_alias`.
> Для каждого нужного УГО выбирай точный `part_id` и оба SHA
> каталога; глядя на SVG/PNG, оцени только графику, а физику
> контактов бери из typed PartDefinition/PinRef.
> Особые признаки: R5=`resistor.variable`, L1/L2
> `inductor.ferromagnetic`, VT1 `transistor.mosfet_n_enh`,
> VD1 `diode.schottky`, FU1 `fuse.general`,
> C1/C2/C3/C5/C6 `capacitor.polarized`,
> C4/C7 `capacitor.fixed`.
>
> Проверки, которые нужно привести в отчёте:
> `source-typed-request.json`, реальные ошибки отказов CLI,
> source/model/catalog SHA, отсутствующие manufacturer/package
> или routing dependencies, ограничения печати.
> Любая пользовательская Netlist без явного подтверждения имеет
> `USER_REVIEW_REQUIRED`. УГО остаются DRAFT.
>
> Если нельзя создать полную 23/15/62/16 печатную E3 без 15/15,
> глобального DRC, настоящего SVG/PNG 300 DPI и QA, верни
> `BLOCKED_PARTIAL`. Не объявляй готовой старую схему
> с 9 ERROR и 32 WARNING или частичный маршрут 10/15.
> Никогда не придумывай tool write/commit, physical Net из текста
> `VCC/GND` или из пикселей SVG.

## Автоматическая проверка доступных инструментов (не запуск LLM)

```bash
python -m pip install -e ".[dev,mcp]"
mkdir -p output
python -m examples.agent_tl494_cycle13_quickstart --out output/tl494-cycle13-user
codex --version
codex mcp add gost-schematic-readonly -- python -m gost_schematic.mcp_server
codex mcp list
codex exec --help
```

Результат `source-quickstart-report.json` должен содержать
`status=BLOCKED_PARTIAL`, `refusal_tests_passed=11`,
`actual_native_mcp_client_session=true`,
`actual_codex_cli_llm_session=false`,
`mcp_write_tool_enabled=false`. Это корректное инженерное
свидетельство, **не** финальная E3 схема.

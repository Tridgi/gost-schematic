# Cycle 13 — TL494CN: воспроизводимый AI/CLI/MCP quickstart

**Реализовано: read-only инженерная подготовка, не выпуск полной схемы.**

## Реальный запуск

Из checkout существующего Draft PR #111, Python 3.12 или 3.13:

```bash
python -m pip install -e ".[dev,mcp]"
python -m ruff check .
python -m pytest -q tests/agent_project/test_agent_tl494_cycle13_quickstart.py
mkdir -p output
python -m examples.agent_tl494_cycle13_quickstart --out output/tl494-cycle13-user
```

`output/tl494-cycle13-user` обязан НЕ существовать до запуска. Выход
без перенаправлений по symlink, без перезаписи; файлы пишет только
доверенный локальный CLI. Сервер MCP сохраняет политику read-only.

Не требуются ключ модели Codex или GitHub API. Встроенная исходная
фикстура IC #97 сверяется с точным Git-blob
`a5c116d8745fadbc14d8f6869e1e7b0f97ff6d65`.
Зафиксированный список HEAD и Git-blob владельцев включён в wheel,
но этот быстрый запуск НЕ скачивает последние живые версии owner PR.
Для проверки шести реальных owner-файлов — отдельная
[инструкция](agent-cycle11-source-driven-walkthrough.md).

## Выходные файлы и доказательства

| Артефакт | Доказано | Не доказано |
|---|---|---|
| `source-typed-request.json` | Настоящий исходный BOM из **23 компонентов**, **15 именованных Net**, **62 уникальных PinRef**, все **16 DA1**, исходные part ID и номиналы | Готовность записать E3 |
| `source-validation.json` | Реальный subprocess типизированного CLI, ожидаемый exit 2 / `BLOCKED_SOURCE_NOT_IMPORTABLE` | Печатный DRC |
| `refusal-tests.json` | 11 реальных отказов CLI: неправильный R5, неизвестное УГО, чужой PinRef, изменение b-Net, неверный номинал, alias R1, stale revision, попытка write, недопустимый output/retries | Автоматический роутер |
| 7 `*.svg` + 7 `*.png` | Настоящие нативные изображения **отдельных каталожных УГО**, полученные через `mcp.ClientSession`, SHA256 каждого | Полный SVG/PNG 300 DPI схемы |
| `source-quickstart-report.json` | Машинные статусы, SHA и размеры артефактов, source 91 исторический wire / 37 junction / 2 графических b | Производственная приёмка |

Статус **`BLOCKED_PARTIAL`** — ожидаемый. Запуск возвращает 0 только
если корректно установлено, что состав исходника верен, а генерация
**НЕ** выполнена. `new_routed_net_count=0` здесь означает, что
этот read-only сценарий **вообще не вызывает роутер**. Он не
опровергает отдельный результат NET владельца 10/15.

Не объявлять пользовательское согласие без действия пользователя:
`source_netlist_user_approval=USER_REVIEW_REQUIRED`. Все УГО без
отдельной нормативной проверки **DRAFT**. Замороженная старая схема
с 9 ERROR / 32 WARNING — негативный контроль.

## Использование реального Codex CLI

```bash
codex --version
codex mcp add gost-schematic-readonly -- python -m gost_schematic.mcp_server
codex mcp list
codex exec --help
```

Эти команды проверяются на настоящем бинарнике в
`ai-codex-cli-cycle11-smoke.yml` на обеих версиях Python. Наличие
MCP в `codex mcp list` **не означает**, что был вызван LLM или
создана физическая схема.

Задача для агента: изучить [AGENTS.md](../../AGENTS.md) и
[Skill](../../skills/gost-schematic/SKILL.md), запросить только
существующие вызовы `schematic_tl494_selection_profile`,
`schematic_catalog_search`, `schematic_catalog_select`,
`schematic_catalog_preview` и `schematic_tl494_pin_alias`,
сопоставить полученные part/symbol SHA с исходником и
вернуть структурированный отчёт `BLOCKED`, а не придумать write tool.

## Что остаётся до реального AI → готовая схема

1. Пользователь проверяет и подтверждает 23 исходных компонента,
   их `source_part_id`/`nominal_si`, 15 точных Net и 62 PinRef.
2. IC #97/RECON #115 предоставляют в доверенном native Circuit
   реальный 16-pin TI package, точный `reference.tl494cn` →
   `ti.tl494cn.pdip16` adapter и два **неэлектрических**
   `b-X2`/`b-R5`; 13 нужных УГО выбираются по точным SHA.
3. NET #114 строит **15/15** на настоящем `ExternalWireGraph`;
   текущий независимо проверенный результат 10/15 — недостаточен.
4. PAINT/ESKD проверяют полный геометрический DRC, A3 либо законный
   A2/многолист, затем формируют **SVG clean/diagnostic, PNG 300 DPI,
   BOM, Netlist и DRC report**. QA проверяет исходную топологию
   и фото только при доступном оригинальном bitmap.
5. Лишь отдельный согласованный P1.2 может открыть будущие
   транзакции с `expected_revision` + `expected_generation`, CAS,
   idempotency, атомарным rollback, строгой проверкой PinRef/Net
   и host authorization. Сейчас **никаких MCP write/edit/commit**.

Никакого создания физических Net по пикселям SVG/PNG.

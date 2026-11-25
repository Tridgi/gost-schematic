import { useEffect, useRef, useState, type ReactNode, type PointerEvent as ReactPointerEvent } from 'react';
import {
  ActionIcon, AppShell, Badge, Button, Divider, Group, MantineProvider, Menu,
  Modal, NavLink, ScrollArea, SegmentedControl, Stack, Switch, Tabs,
  Text, TextInput, Tooltip, useAppShellResize
} from '@mantine/core';
import { useLocalStorage } from '@mantine/hooks';
import {
  AlertTriangle, Cable, FileDown, FolderTree, Grid3X3, Hand,
  Magnet, Menu as MenuIcon, MousePointer2, Save, Search, Settings2,
  Undo2, Redo2, Type as TypeIcon, Moon, Sun, CircleDot
} from 'lucide-react';
import { normalizeDockLayout, DOCK_LAYOUT_KEY, type DockLayout } from '../theme/layout';
import { formatMillimetres, parseMillimetres } from './inspector-units';
import { resolveShellShortcut } from './shortcuts';
import '../theme/design-tokens.css';

export type ToolMode = 'select' | 'wire' | 'text' | 'pan' | 'junction' | 'place';
export type CatalogSymbol = {
  id: string; name: string; category: string; approval: 'draft' | 'approved' | 'blocked';
  /** Trusted SVG ReactNode from canonical catalogue renderer; no icon-based UGO substitution. */
  thumbnail: ReactNode;
};
export type TreeItem = { id: string; label: string; kind: 'sheet' | 'instance' | 'net' | 'wire' | 'graphic'; indent?: number };
export type SelectedInstance = {
  id: string; refdes: string; value: string; originUm: readonly [number,number];
  rotationDeg: 0|90|180|270; physicalPins: readonly { number:string; netName:string|null }[];
};
export type DiagnosticItem = {id:string; severity:'error'|'warning'|'info'; message:string;code?:string;instanceId?:string};
export type InspectorProposal =
  | {kind:'propose-origin-axis';instanceId:string;axis:'x'|'y';um:number;baseRevision:string}
  | {kind:'propose-refdes';instanceId:string;refdes:string;baseRevision:string}
  | {kind:'propose-value';instanceId:string;value:string;baseRevision:string};

/** The host owns all electrical topology, source PinRefs, command validation and actual persistence. */
export type EditorShellProps = {
  projectName:string;dirty:boolean;baseRevision:string;
  sheets:readonly {id:string;title:string}[];activeSheetId:string;
  catalog:readonly CatalogSymbol[];tree:readonly TreeItem[];
  catalogMissingCount?:number;onCatalogUpgrade?:()=>void;
  selected:SelectedInstance|null;groupSelectionIds?:readonly string[];diagnostics:readonly DiagnosticItem[];diagnosticCounts?:{error:number;warning:number;info:number};
  clipboardSummary?:string;
  canvas:ReactNode;tool:ToolMode;gridVisible:boolean;snapEnabled:boolean;
  cursorUm?:readonly [number,number];zoomPercent?:number;onZoomPercent?:(percent:50|100|200)=>void;
  onFitPage?:()=>void;
  canUndo:boolean;canRedo:boolean;canSave:boolean;exportReady:boolean;
  /** Authoritative CAS rejection/validation feedback from host model, not optimistically hidden. */
  inspectorError?:string|null;
  onToolChange:(tool:ToolMode)=>void;
  onToggleGrid:(v:boolean)=>void;onToggleSnap:(v:boolean)=>void;
  onPlaceSymbol:(symbolId:string)=>void;onSelectTreeItem:(id:string)=>void;
  onSelectSheet:(id:string)=>void;onInspectorProposal:(edit:InspectorProposal)=>void;
  onUndo:()=>void;onRedo:()=>void;onSave:()=>void;
  onCopy?:()=>void;onPaste?:()=>void;
  smartRouting?:boolean;onToggleSmartRouting?:(enabled:boolean)=>void;onAlignConnectedPair?:()=>void;
  onOpen?:()=>void;onNew?:()=>void;onAddSheet?:()=>void;
  onPaperChange?:(paper:'A4'|'A3'|'A2')=>void;activePaper?:'A4'|'A3'|'A2';
  onSaveAs?:()=>void;onExport?:(format:'svg'|'png300')=>void;
};

function NumericAxis({selected,axis,revision,send}:{
  selected:SelectedInstance;axis:'x'|'y';revision:string;send:(edit:InspectorProposal)=>void
}) {
  const current=selected.originUm[axis==='x'?0:1];
  const [draft,setDraft]=useState(()=>formatMillimetres(current));
  const [error,setError]=useState<string|null>(null);
  useEffect(()=>{setDraft(formatMillimetres(current));setError(null);},[current,selected.id]);
  function commit(){
    const value=parseMillimetres(draft);
    if(!value.ok){
      setError({EMPTY:'Укажите координату',INVALID_FORMAT:'Неверное десятичное число',PRECISION:'Точность 0,001 мм',OUT_OF_RANGE:'Координата вне диапазона'}[value.code]);
      return;
    }
    setError(null);setDraft(formatMillimetres(current));
    if(value.um!==current) send({kind:'propose-origin-axis',instanceId:selected.id,axis,um:value.um,baseRevision:revision});
  }
  return <TextInput size="xs" label={axis.toUpperCase()+', мм'} value={draft} error={error}
    onChange={e=>{setDraft(e.currentTarget.value);setError(null);}}
    onBlur={commit} onKeyDown={e=>{if(e.key==='Enter')e.currentTarget.blur(); if(e.key==='Escape'){setDraft(formatMillimetres(current));setError(null);e.stopPropagation();}}}
    data-testid={'inspector-axis-'+axis}
    aria-label={'Координата '+axis.toUpperCase()+' в миллиметрах'}/>;
}

function Inspector({selected,revision,send,hostError}:{
  selected:SelectedInstance|null;revision:string;send:(edit:InspectorProposal)=>void;hostError?:string|null
}){
  const [refdes,setRefdes]=useState(selected?.refdes??'');
  const [valueDraft,setValueDraft]=useState(selected?.value??'');
  useEffect(()=>setRefdes(selected?.refdes??''),[selected?.id,selected?.refdes]);
  useEffect(()=>setValueDraft(selected?.value??''),[selected?.id,selected?.value]);
  if(!selected)return <Text size="sm" c="dimmed" p="md">Выберите элемент для просмотра свойств.</Text>;
  const refdesCommit=()=>{
    const v=refdes.trim();
    if(v&&v!==selected.refdes)send({kind:'propose-refdes',instanceId:selected.id,refdes:v,baseRevision:revision});
    setRefdes(selected.refdes);
  };
  const valueCommit=()=>{
    const v=valueDraft.trim();
    if(v!==selected.value && v.length<=128)send({kind:'propose-value',instanceId:selected.id,value:v,baseRevision:revision});
    setValueDraft(selected.value); // Host must confirm/deny revision; never pretend a commit succeeded.
  };
  return <Stack p="sm" gap="xs" data-testid="inspector">
    <Text size="xs" c="dimmed">ID: {selected.id}</Text>
    <TextInput size="xs" label="Позиционное обозначение" value={refdes}
      onChange={e=>setRefdes(e.currentTarget.value)} onBlur={refdesCommit}
      onKeyDown={e=>{if(e.key==='Enter')e.currentTarget.blur();if(e.key==='Escape'){setRefdes(selected.refdes);e.stopPropagation();}}}/>
    <TextInput size="xs" label="Номинал" value={valueDraft} data-testid="inspector-nominal"
      maxLength={128} description="Изменение требует подтверждения доменной модели"
      onChange={e=>setValueDraft(e.currentTarget.value)} onBlur={valueCommit}
      onKeyDown={e=>{if(e.key==='Enter')e.currentTarget.blur();if(e.key==='Escape'){setValueDraft(selected.value);e.stopPropagation();}}}/>
    {hostError&&<Text size="xs" c="red" role="alert" data-testid="inspector-host-error">{hostError}</Text>}
    <Group grow wrap="nowrap" gap="xs">
      <NumericAxis selected={selected} axis="x" revision={revision} send={send}/>
      <NumericAxis selected={selected} axis="y" revision={revision} send={send}/>
    </Group>
    <Text size="xs">Поворот: {selected.rotationDeg}°</Text>
    <Divider label="Физические выводы — только чтение"/>
    {selected.physicalPins.map(pin=><Group key={pin.number} justify="space-between">
      <Text size="xs">№ {pin.number}</Text><Text c="dimmed" size="xs">{pin.netName??'Без Net'}</Text>
    </Group>)}
  </Stack>;
}

function RightSplit({top,bottom,percent,onChange}:{
  top:ReactNode;bottom:ReactNode;percent:number;onChange:(p:number)=>void
}){
  const root=useRef<HTMLDivElement>(null);
  const drag=useRef<{y:number;start:number;height:number}|null>(null);
  const clamp=(v:number)=>Math.max(25,Math.min(75,v));
  return <div ref={root} className="gscad-right-dock"
    style={{gridTemplateRows:'minmax(80px,'+percent+'fr) 8px minmax(100px,'+(100-percent)+'fr)'}}>
    <section className="gscad-dock-section" aria-label="Структура проекта">{top}</section>
    <div className="gscad-vsplit" role="separator" tabIndex={0} aria-orientation="horizontal"
      aria-label="Изменить высоту дерева и инспектора" aria-valuemin={25} aria-valuemax={75}
      aria-valuenow={Math.round(percent)}
      onPointerDown={(e:ReactPointerEvent<HTMLDivElement>)=>{
        if(!root.current)return;
        e.currentTarget.setPointerCapture(e.pointerId);
        drag.current={y:e.clientY,start:percent,height:Math.max(1,root.current.clientHeight)};
      }}
      onPointerMove={(e:ReactPointerEvent<HTMLDivElement>)=>{
        if(!drag.current)return;
        const d=drag.current;onChange(clamp(d.start+(e.clientY-d.y)*100/d.height));
      }}
      onPointerUp={(e:ReactPointerEvent<HTMLDivElement>)=>{
        drag.current=null;e.currentTarget.releasePointerCapture(e.pointerId);
      }}
      onPointerCancel={()=>{drag.current=null;}}
      onKeyDown={e=>{
        if(!['ArrowUp','ArrowDown','Home','End'].includes(e.key))return;
        e.preventDefault();
        onChange(e.key==='Home'?25:e.key==='End'?75:clamp(percent+(e.key==='ArrowDown'?1:-1)*(e.shiftKey?10:5)));
      }}/>
    <section className="gscad-dock-section" aria-label="Свойства">{bottom}</section>
  </div>;
}

function ShellView(props:EditorShellProps & {scheme:'dark'|'light';setScheme:(v:'dark'|'light')=>void}){
  const [sizes,setSizes]=useLocalStorage<DockLayout>({key:DOCK_LAYOUT_KEY,defaultValue:{}});
  const [left,setLeft]=useState(()=>typeof window==='undefined'||window.innerWidth>=960);
  const [right,setRight]=useState(()=>typeof window==='undefined'||window.innerWidth>=960);
  const [settings,setSettings]=useState(false),[exportDialog,setExportDialog]=useState(false);
  const [commandDialog,setCommandDialog]=useState(false),[diagnostics,setDiagnostics]=useState(false);
  const [diagnosticFilter,setDiagnosticFilter]=useState<'all'|'error'|'warning'|'info'>('all');
  const diagnosticCounts=props.diagnosticCounts??{error:props.diagnostics.filter(d=>d.severity==='error').length,warning:props.diagnostics.filter(d=>d.severity==='warning').length,info:props.diagnostics.filter(d=>d.severity==='info').length};
  const diagnosticItems=props.diagnostics.filter(d=>diagnosticFilter==='all'||d.severity===diagnosticFilter);
  const [query,setQuery]=useState(''),[commandQuery,setCommandQuery]=useState('');
  const [format,setFormat]=useState<'svg'|'png300'>('svg');
  const [split,setSplit]=useState(()=>normalizeDockLayout(sizes).inspectorPercent??48);
  // Mantine useLocalStorage reads existing preferences in an effect; restore after hydration.
  useEffect(()=>{if(typeof sizes.inspectorPercent==='number')setSplit(Math.min(75,Math.max(25,sizes.inspectorPercent)));},[sizes.inspectorPercent]);
  const viewport=typeof window==='undefined'?1440:window.innerWidth;
  const persisted=normalizeDockLayout(sizes,viewport);
  const resize=useAppShellResize({
    navbar:{min:200,max:420,label:'Ширина библиотеки УГО'},
    aside:{min:260,max:460,label:'Ширина панели свойств'},
    initialSizes:{navbar:persisted.navbar,aside:persisted.aside},
    onResizeEnd:changed=>setSizes(normalizeDockLayout({...sizes,...changed,inspectorPercent:split},window.innerWidth))
  });
  function resetLayout(){resize.resetAll();setSizes({});setSplit(48);const wide=typeof window==='undefined'||window.innerWidth>=960;setLeft(wide);setRight(wide);}
  function changeSplit(p:number){setSplit(p);setSizes({...sizes,inspectorPercent:p});}
  const filtered=props.catalog.filter(x=>(x.name+' '+x.category+' '+x.id).toLocaleLowerCase('ru-RU').includes(query.toLocaleLowerCase('ru-RU')));
  useEffect(()=>{
    const onKey=(e:globalThis.KeyboardEvent)=>{
      const editable=!!(e.target as HTMLElement)?.closest('input,textarea,select,[contenteditable="true"],[role="textbox"]');
      // The browser Save-as dialog would incorrectly capture an uncommitted inspector draft.
      if(editable&&(e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();return;}
      const action=resolveShellShortcut(e,{editable,dialogOpen:settings||exportDialog||commandDialog});
      if(!action)return;
      if(action==='save'&&!props.canSave || action==='undo'&&!props.canUndo || action==='redo'&&!props.canRedo)return;
      if(action==='copy'&&!props.onCopy || action==='paste'&&!props.onPaste)return;
      e.preventDefault();
      if(action==='palette')setCommandDialog(true);
      else if(action==='export')setExportDialog(true);
      else if(action==='save')props.onSave();
      else if(action==='undo')props.onUndo();
      else if(action==='redo')props.onRedo();
      else if(action==='copy')props.onCopy?.();
      else if(action==='paste')props.onPaste?.();
      else props.onToolChange(action);
    };
    window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey);
  },[props.onToolChange,props.onSave,props.onUndo,props.onRedo,props.canSave,props.canUndo,props.canRedo,props.onCopy,props.onPaste,settings,exportDialog,commandDialog]);
  const commands=[
    {label:'Сохранить',ok:props.canSave,run:props.onSave},
    {label:'Экспорт',ok:true,run:()=>setExportDialog(true)},
    {label:'Настройки',ok:true,run:()=>setSettings(true)},
    {label:'Сбросить панели',ok:true,run:resetLayout}
  ].filter(a=>a.label.toLocaleLowerCase('ru-RU').includes(commandQuery.toLocaleLowerCase('ru-RU')));
  return <>
    <AppShell padding={0} header={{height:56}} footer={{height:30}}
      navbar={{width:256,breakpoint:'md',collapsed:{mobile:!left,desktop:!left}}}
      aside={{width:318,breakpoint:'md',collapsed:{mobile:!right,desktop:!right}}}
      resize={resize} transitionDuration={0}>
      <AppShell.Header className="gscad-header" data-testid="project-toolbar">
        <Group justify="space-between" h="100%" px="sm" gap="xs" wrap="nowrap">
          <Group gap="xs" wrap="nowrap">
            <ActionIcon aria-label="Показать библиотеку УГО" variant="subtle" onClick={()=>setLeft(v=>!v)}><MenuIcon size={18}/></ActionIcon>
            <Text size="sm" fw={700} visibleFrom="sm">GOST CAD</Text>
            <Menu position="bottom-start"><Menu.Target><Button variant="subtle" size="compact-sm">Файл</Button></Menu.Target>
              <Menu.Dropdown>
                <Menu.Item data-testid="new-project" onClick={props.onNew} disabled={!props.onNew}>Новый проект A3</Menu.Item>
                <Menu.Item data-testid="new-sheet" onClick={props.onAddSheet} disabled={!props.onAddSheet}>Добавить лист A3</Menu.Item>
                <Menu.Divider/>
                {(['A4','A3','A2'] as const).map(paper=><Menu.Item
                  key={paper} data-testid={'paper-format-'+paper}
                  disabled={!props.onPaperChange||props.activePaper===paper}
                  onClick={()=>props.onPaperChange?.(paper)}>
                  Лист {paper} — альбомный{props.activePaper===paper?' (текущий)':''}
                </Menu.Item>)}
                <Menu.Divider/>
                <Menu.Item onClick={props.onOpen} disabled={!props.onOpen}>Открыть…</Menu.Item>
                <Menu.Item onClick={props.onSave} disabled={!props.canSave}>Сохранить</Menu.Item>
                <Menu.Item data-testid="save-project-as" onClick={props.onSaveAs} disabled={!props.onSaveAs}>Сохранить как…</Menu.Item>
                <Menu.Item onClick={()=>setExportDialog(true)}>Экспорт…</Menu.Item>
              </Menu.Dropdown>
            </Menu>
            <Menu position="bottom-start"><Menu.Target><Button variant="subtle" size="compact-sm">Правка</Button></Menu.Target>
              <Menu.Dropdown>
                <Menu.Item data-testid="copy-component" onClick={props.onCopy} disabled={!props.onCopy}>Копировать выделенное · Ctrl+C</Menu.Item>
                <Menu.Item data-testid="smart-routing" disabled={!props.onToggleSmartRouting} onClick={()=>props.onToggleSmartRouting?.(!props.smartRouting)}>Умная трассировка: {props.smartRouting?'вкл.':'выкл.'}</Menu.Item>
                <Menu.Item data-testid="align-connected-pair" disabled={!props.onAlignConnectedPair} onClick={props.onAlignConnectedPair}>Выровнять соединённые выводы</Menu.Item>
                <Menu.Divider/>
                <Menu.Item data-testid="paste-component" onClick={props.onPaste} disabled={!props.onPaste}>Вставить независимую копию · Ctrl+V</Menu.Item>
              </Menu.Dropdown>
            </Menu>
            <Text size="sm" fw={600} truncate className="gscad-project-label">{props.projectName}</Text>
            {props.dirty&&<Badge size="xs" color="yellow">Не сохранено</Badge>}
          </Group>
          <Group gap={4} wrap="nowrap">
            <ActionIcon aria-label="Отменить" variant="subtle" disabled={!props.canUndo} onClick={props.onUndo}><Undo2 size={17}/></ActionIcon>
            <ActionIcon aria-label="Повторить" variant="subtle" disabled={!props.canRedo} onClick={props.onRedo}><Redo2 size={17}/></ActionIcon>
            <ActionIcon aria-label="Сохранить" data-testid="save-project" variant="subtle" disabled={!props.canSave} onClick={props.onSave}><Save size={17}/></ActionIcon>
            <ActionIcon aria-label="Команды Ctrl+K" variant="subtle" onClick={()=>setCommandDialog(true)}><Search size={17}/></ActionIcon>
            <ActionIcon aria-label="Настройки" variant="subtle" onClick={()=>setSettings(true)}><Settings2 size={17}/></ActionIcon>
            <ActionIcon aria-label="Переключить тему" data-testid="toggle-theme" variant="subtle" onClick={()=>props.setScheme(props.scheme==='dark'?'light':'dark')}>{props.scheme==='dark'?<Sun size={17}/>:<Moon size={17}/>}</ActionIcon>
            <ActionIcon aria-label="Показать инспектор" variant="subtle" onClick={()=>setRight(v=>!v)}><FolderTree size={17}/></ActionIcon>
            <Button leftSection={<FileDown size={15}/>} size="compact-sm" onClick={()=>setExportDialog(true)}>Экспорт</Button>
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar className="gscad-dock">
        <Stack gap="xs" p="sm" h="100%">
          <Text size="sm" fw={600}>Библиотека УГО · {props.catalog.length}</Text>
          {!!props.catalogMissingCount&&<Button size="compact-xs" variant="light" data-testid="upgrade-catalog" onClick={props.onCatalogUpgrade}>Добавить УГО (+{props.catalogMissingCount})</Button>}
          <TextInput size="xs" aria-label="Поиск УГО" leftSection={<Search size={14}/>}
            placeholder="Поиск по каталогу" value={query} onChange={e=>setQuery(e.currentTarget.value)} data-testid="catalog-search"/>
          <ScrollArea h="100%" type="hover"><Stack gap={4}>
            {filtered.map(s=><Button key={s.id} size="compact-lg" variant="subtle" className="gscad-catalog-item" data-testid={'catalog-item-'+s.id}
              aria-label={'Выбрать УГО '+s.name+', '+s.approval} title={s.id} onClick={()=>props.onPlaceSymbol(s.id)}>
              <span className="gscad-symbol-preview" aria-hidden="true">{s.thumbnail??'Нет эскиза'}</span>
              <span className="gscad-symbol-info"><span>{s.name}</span><small>{s.category} · {s.approval}</small></span>
            </Button>)}
            {filtered.length===0&&<Text size="sm" c="dimmed">Совпадений нет</Text>}
          </Stack></ScrollArea>
        </Stack>
      </AppShell.Navbar>
      <AppShell.Main className="gscad-center"><div className="gscad-center-inner">
        <Tabs value={props.activeSheetId} onChange={id=>{if(id)props.onSelectSheet(id);}} keepMounted={false} className="gscad-sheet-tabs">
          <Tabs.List>{props.sheets.map(s=><Tabs.Tab key={s.id} value={s.id}>{s.title}</Tabs.Tab>)}</Tabs.List>
        </Tabs>
        <div className="gscad-canvas-slot" data-testid="gscad-canvas-slot" role="region" aria-label="Область схемы">
          {props.canvas??<Text size="sm" c="dimmed">CAD-холст не подключён</Text>}
        </div>
        <Group className="gscad-toolbar" px="sm" gap={4} wrap="nowrap">
          {([
            ['select',MousePointer2,'Выбор V'],['wire',Cable,'Провод W'],
            ['text',TypeIcon,'Текст T'],['pan',Hand,'Панорама H'],
            ['junction',CircleDot,'Явный узел J']
          ] as const).map(([mode,Icon,label])=>
            <Tooltip key={mode} label={label}><ActionIcon size="lg" variant={props.tool===mode?'filled':'subtle'}
              aria-label={label} data-testid={'tool-'+mode} aria-pressed={props.tool===mode} onClick={()=>props.onToolChange(mode)}>
              <Icon size={18}/></ActionIcon></Tooltip>)}
          <Divider orientation="vertical"/>
          <Tooltip label="Показать сетку"><ActionIcon size="lg" aria-label="Показать сетку" data-testid="toggle-grid-visible" aria-pressed={props.gridVisible}
            variant={props.gridVisible?'light':'subtle'} onClick={()=>props.onToggleGrid(!props.gridVisible)}>
            <Grid3X3 size={18}/></ActionIcon></Tooltip>
          <Tooltip label="Привязка"><ActionIcon size="lg" aria-label="Привязка к сетке" data-testid="toggle-grid-snap" aria-pressed={props.snapEnabled}
            variant={props.snapEnabled?'light':'subtle'} onClick={()=>props.onToggleSnap(!props.snapEnabled)}>
            <Magnet size={18}/></ActionIcon></Tooltip>
          <div className="gscad-toolbar-spacer"/>
          <Button size="compact-sm" variant="subtle" leftSection={<AlertTriangle size={15}/>}
            onClick={()=>setDiagnostics(v=>!v)}>ERC/DRC · {diagnosticCounts.error} ошибок / {diagnosticCounts.warning} предупреждений</Button>
        </Group>
        {diagnostics&&<div className="gscad-diagnostics" aria-label="Журнал диагностики" data-testid="diagnostics-panel">
          <Group gap={4} p={4}>
            {(['all','error','warning','info'] as const).map(f=><Button key={f} size="compact-xs"
              variant={diagnosticFilter===f?'filled':'subtle'} data-testid={'diagnostic-filter-'+f}
              onClick={()=>setDiagnosticFilter(f)}>{f==='all'?'Все':(f==='error'?'Ошибки':f==='warning'?'Предупреждения':'Информация')+' ('+diagnosticCounts[f]+')'}</Button>)}
          </Group>
          <ScrollArea h={120}>
            {diagnosticItems.length===0?<Text size="sm" p="sm">Сообщений нет в этом фильтре. Это не доказывает корректность схемы.</Text>:
              diagnosticItems.map(d=><Group key={d.id} gap={4} p={4} wrap="nowrap" align="start" data-diagnostic-code={d.code??d.id} data-severity={d.severity}>
                <Text size="xs" c={d.severity==='error'?'red':d.severity==='warning'?'yellow':undefined} style={{flex:1}}>[{d.code??d.severity}] {d.message}</Text>
                {d.instanceId&&<Button size="compact-xs" variant="subtle" onClick={()=>props.onSelectTreeItem(d.instanceId!)}>Выбрать УГО</Button>}
              </Group>)}
          </ScrollArea>
        </div>}
      </div></AppShell.Main>
      <AppShell.Aside className="gscad-dock">
        <RightSplit percent={split} onChange={changeSplit}
          top={<><Text size="sm" fw={600} p="sm">Структура проекта</Text>
            <ScrollArea h="calc(100% - 44px)">{props.tree.map(n=><NavLink key={n.id} label={n.label} data-testid={'tree-item-'+n.id}
              pl={12+(n.indent??0)*16} active={n.kind==='instance'&&(n.id===props.selected?.id||props.groupSelectionIds?.includes(n.id))} onClick={()=>props.onSelectTreeItem(n.id)}
              leftSection={<FolderTree size={14}/>} />)}</ScrollArea></>}
          bottom={<><Text fw={600} size="sm" p="sm">Свойства</Text>
            <ScrollArea h="calc(100% - 44px)">{(props.groupSelectionIds?.length??0)>1?<Text size="sm" p="sm" data-testid="group-selection-summary">Выбрано УГО: {props.groupSelectionIds?.length}. Групповое изменение свойств пока недоступно.{props.onAlignConnectedPair&&<Button fullWidth size="xs" mt="xs" data-testid="align-connected-pair-inspector" onClick={props.onAlignConnectedPair}>Выровнять выводы</Button>}</Text>:<Inspector selected={props.selected}
              revision={props.baseRevision} send={props.onInspectorProposal} hostError={props.inspectorError}/>}</ScrollArea></>}/>
      </AppShell.Aside>
      <AppShell.Footer className="gscad-status" data-testid="status-bar">
        <Group justify="space-between" h="100%" px="xs" gap="xs" wrap="nowrap">
          <Text size="xs">{props.cursorUm?'X '+formatMillimetres(props.cursorUm[0])+' / Y '+formatMillimetres(props.cursorUm[1])+' мм':'XY —'}</Text>
          {props.clipboardSummary&&<Text size="xs" truncate title={props.clipboardSummary} data-testid="clipboard-summary" role="status">{props.clipboardSummary}</Text>}
          <Group gap="xs" wrap="nowrap">
            <Menu position="top-end" withinPortal>
              <Menu.Target><Button size="compact-xs" variant="subtle" aria-label="Масштаб">{props.zoomPercent??100}%</Button></Menu.Target>
              <Menu.Dropdown>
                <Menu.Item data-testid="fit-page" onClick={props.onFitPage}
                  disabled={!props.onFitPage}>Вписать лист и содержимое</Menu.Item>
                <Menu.Divider/>
                {([50,100,200] as const).map(pct=><Menu.Item key={pct}
                  onClick={()=>props.onZoomPercent?.(pct)}>{pct}%</Menu.Item>)}
              </Menu.Dropdown>
            </Menu>
            <Text size="xs">Сетка {props.gridVisible?'ON':'OFF'}</Text><Text size="xs">Snap {props.snapEnabled?'ON':'OFF'}</Text>
            <Text size="xs">{props.dirty?'Не сохранено':'Сохранено'}</Text>
          </Group>
        </Group>
      </AppShell.Footer>
    </AppShell>
    <Modal opened={settings} onClose={()=>setSettings(false)} title="Настройки интерфейса" centered>
      <Stack><SegmentedControl value={props.scheme} onChange={v=>props.setScheme(v as 'dark'|'light')}
        data={[{label:'Тёмная',value:'dark'},{label:'Светлая',value:'light'}]} fullWidth/>
        <Switch label="Показывать сетку" checked={props.gridVisible}
          onChange={e=>props.onToggleGrid(e.currentTarget.checked)}/>
        <Switch label="Привязка к сетке" checked={props.snapEnabled}
          onChange={e=>props.onToggleSnap(e.currentTarget.checked)}/>
        <Button variant="light" onClick={resetLayout}>Сбросить панели</Button>
      </Stack>
    </Modal>
    <Modal opened={exportDialog} onClose={()=>setExportDialog(false)} title="Экспорт схемы" centered>
      <Stack><SegmentedControl fullWidth value={format} onChange={v=>setFormat(v as 'svg'|'png300')}
        data={[{label:'SVG',value:'svg'},{label:'PNG 300 DPI',value:'png300'}]}/>
        {!props.exportReady&&<Text size="sm" c="dimmed">Канонический экспорт не подтверждён.</Text>}
        <Button disabled={!props.exportReady||!props.onExport}
          onClick={()=>{props.onExport?.(format);setExportDialog(false);}}>Экспортировать</Button>
      </Stack>
    </Modal>
    <Modal opened={commandDialog} onClose={()=>setCommandDialog(false)} title="Команды" centered data-testid="command-palette">
      <TextInput value={commandQuery} onChange={e=>setCommandQuery(e.currentTarget.value)}
        placeholder="Поиск команды" aria-label="Поиск команды" autoFocus/>
      <Stack gap={4} mt="sm">{commands.map(a=><Button key={a.label} variant="subtle" justify="flex-start"
        disabled={!a.ok} onClick={()=>{setCommandDialog(false);a.run();}}>{a.label}</Button>)}</Stack>
    </Modal>
  </>;
}

export function EditorShell(props:EditorShellProps){
  const [stored,setStored]=useLocalStorage<'dark'|'light'>({key:'gscad:ui:theme:v1',defaultValue:'dark'});
  const scheme=stored==='light'?'light':'dark';
  return <MantineProvider forceColorScheme={scheme}>
    <div className="gscad-app" data-testid="editor-root">
      <ShellView {...props} scheme={scheme} setScheme={setStored}/>
    </div>
  </MantineProvider>;
}

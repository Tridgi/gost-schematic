import {demo,deep,uid,UM,LIBRARY,verifyProject,serialized,sheet,resolvePin,snap,routePoints,appendWire,moveSegment,reanchor,nextReference,pointOnSegment,symbolArtwork,exportSvg,withPngDpi,removeWire} from './core.mjs';
const $=id=>document.getElementById(id);
const canvas=$('canvas');
let project=demo(),currentSheet='sheet-1',selection=null,tool='select',placing=null,startPin=null,waypoints=[],hover=null,drag=null,gridVisible=true,gridSnap=true,gridStep=5000,dirty=false;
let camera={x:-21000,y:-13000,w:462000,h:323000};
const history=[],future=[];
const s=()=>sheet(project,currentSheet);
function stateMessage(v){$('status-msg').textContent=v;}
function changeMarker(){dirty=true;$('dirty').textContent='●';try{localStorage.setItem('gscad-r0-recovery',serialized(project));}catch(e){stateMessage(`Автовосстановление недоступно: ${e.message}`);}}
function before(){return deep(project);}
function commit(previous){if(JSON.stringify(previous)!==JSON.stringify(project)){try{verifyProject(project);}catch(e){project=previous;selection=null;stateMessage(`Изменение отклонено: ${e.message}`);render();return;}history.push(previous);if(history.length>80)history.shift();future.length=0;changeMarker();}render();}
function undo(){if(!history.length)return;future.push(deep(project));project=history.pop();selection=null;changeMarker();render();}
function redo(){if(!future.length)return;history.push(deep(project));project=future.pop();selection=null;changeMarker();render();}
function setTool(next){tool=next;placing=null;startPin=null;waypoints=[];hover=null;selection=null;render();}
function setTheme(t){document.body.dataset.theme=t;localStorage.setItem('gscad-r0-theme',t);$('theme-select').value=t;}
function active(){return s().symbols.find(x=>x.id===selection?.id);}
function mm(n){return (n/1000).toFixed(3).replace(/\.?0+$/,'')||'0';}
function escapeText(t){return String(t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function stageSize(){const r=canvas.getBoundingClientRect();return {w:r.width||1,h:r.height||1};}
function worldPoint(e){const pt=canvas.createSVGPoint();pt.x=e.clientX;pt.y=e.clientY;const ctm=canvas.getScreenCTM();if(!ctm)return null;const r=pt.matrixTransform(ctm.inverse());return{x:Math.round(r.x*UM),y:Math.round(r.y*UM)};}
function snappedPoint(p){return {x:snap(p.x,gridStep,gridSnap),y:snap(p.y,gridStep,gridSnap)};}
function centerView(){const {w,h}=stageSize();const ratio=w/h;const bw=s().widthUm,bh=s().heightUm;let tw=bw*1.1,th=bh*1.1;if(tw/th<ratio)tw=th*ratio;else th=tw/ratio;camera={x:(bw-tw)/2,y:(bh-th)/2,w:tw,h:th};renderCanvas();}
function projectShape(){return s();}
function renderCanvas(){
  let sh=s();const view=[camera.x,camera.y,camera.w,camera.h].map(mm).join(' ');canvas.setAttribute('viewBox',view);
  const bg=document.body.dataset.theme==='dark'?'#f9fafb':'#fff';
  const grid=gridVisible?`<defs><pattern id="grid" width="${mm(gridStep)}" height="${mm(gridStep)}" patternUnits="userSpaceOnUse"><path d="M ${mm(gridStep)} 0 L 0 0 0 ${mm(gridStep)}" fill="none" stroke="#d5dde5" stroke-width="0.12"/></pattern></defs><rect class="gridlines" x="0" y="0" width="${mm(sh.widthUm)}" height="${mm(sh.heightUm)}" fill="url(#grid)"/>`:'';
  let content=`<rect x="0" y="0" width="${mm(sh.widthUm)}" height="${mm(sh.heightUm)}" fill="${bg}" stroke="#8192a4" stroke-width=".25"/>${grid}`;
  content+=`<g color="#202935" stroke="#202935" stroke-width=".3" fill="none">${sh.symbols.map(symbolArtwork).join('')}</g>`;
  const coords=w=>w.points.map(p=>`${mm(p.x)},${mm(p.y)}`).join(' ');
  for(const w of sh.wires){content+=`<polyline class="draw-wire" points="${coords(w)}" data-net="${escapeText(w.netId)}"/>`;
    for(let i=0;i<w.points.length-1;i++){
      const a=w.points[i],b=w.points[i+1];content+=`<line data-wire="${escapeText(w.id)}" data-seg="${i}" class="hitwire" x1="${mm(a.x)}" y1="${mm(a.y)}" x2="${mm(b.x)}" y2="${mm(b.y)}"/>`;
    }
  }
  for(const g of sh.graphics){if(g.type==='line')content+=`<path d="M ${mm(g.a.x)} ${mm(g.a.y)} L ${mm(g.b.x)} ${mm(g.b.y)}" stroke="black" stroke-width=".3" data-non-electrical="true"/>`;
  }
  for(const j of sh.junctions)content+=`<circle cx="${mm(j.x)}" cy="${mm(j.y)}" r=".7" fill="#121921"/>`;
  if(selection?.type==='symbol'){const a=active();if(a){const w=a.kind==='ic.tl494.demo'?47000:23000,h=a.kind==='ic.tl494.demo'?52000:18000;content+=`<rect class="selection-outline" transform="translate(${mm(a.x)} ${mm(a.y)}) rotate(${a.rotation})" x="${mm(-w/2)}" y="${mm(-h/2)}" width="${mm(w)}" height="${mm(h)}"/>`;}}
  for(const item of sh.symbols){
    const info=LIBRARY[item.kind];
    const w=item.kind==='ic.tl494.demo'?45000:22000,h=item.kind==='ic.tl494.demo'?45000:12000;
    content+=`<rect class="hit-symbol" data-symbol="${escapeText(item.id)}" x="${mm(-w/2)}" y="${mm(-h/2)}" width="${mm(w)}" height="${mm(h)}" transform="translate(${mm(item.x)} ${mm(item.y)}) rotate(${item.rotation})" fill="transparent"/>`;
    if(tool==='wire'||startPin||selection?.id===item.id){
      for(const pin of info.pins){const p=resolvePin(sh,{symbolId:item.id,number:pin.number});content+=`<circle class="pin-target" data-symbol="${escapeText(item.id)}" data-pin="${escapeText(pin.number)}" cx="${mm(p.x)}" cy="${mm(p.y)}" r="1.25"><title>${escapeText(item.ref)}.${pin.number}</title></circle>`;}
    }
  }
  if(startPin&&hover){const from=waypoints.length?waypoints.at(-1):resolvePin(sh,startPin);const points=routePoints(from,hover);const prev=[resolvePin(sh,startPin),...waypoints];const joined=[...prev,...points.slice(1)];content+=`<polyline class="preview" points="${joined.map(p=>`${mm(p.x)},${mm(p.y)}`).join(' ')}"/>`;}
  canvas.innerHTML=content;
  $('zoom-status').textContent=`${Math.round(s().widthUm/camera.w*100)}%`;
}
function renderPalette(){const search=$('search').value.trim().toLowerCase();$('palette').innerHTML=Object.entries(LIBRARY).filter(([k,d])=>(k+' '+d.label).toLowerCase().includes(search)).map(([kind,d])=>`<button class="palette-item" draggable="true" data-kind="${kind}"><span class="palette-symbol">${kind==='resistor.fixed'?'▭':kind==='capacitor.fixed'?'⊣⊢':'▣'}</span><span><strong>${d.label}</strong><small>${kind==='ic.tl494.demo'?'16 физических номеров · демо':`${d.pins.length} вывода · DRAFT`}</small></span></button>`).join('');
  document.querySelectorAll('.palette-item').forEach(btn=>{btn.onclick=()=>{placing=btn.dataset.kind;tool='place';startPin=null;render();};btn.ondragstart=e=>e.dataTransfer.setData('text/x-gscad-kind',btn.dataset.kind);});
}
function renderStructure(){const sh=s();$('object-count').textContent=`${sh.symbols.length} УГО`;
  const symbols=sh.symbols.map(x=>`<button class="tree-item ${selection?.id===x.id?'selected':''}" data-object="${escapeText(x.id)}">◈ ${escapeText(x.ref)} <span>${escapeText(x.value)}</span></button>`).join('');
  const wires=sh.wires.map(w=>`<button class="tree-item ${selection?.id===w.id?'selected':''}" data-wire-object="${escapeText(w.id)}">⌁ ${escapeText(sh.nets.find(n=>n.id===w.netId)?.name||'?')}<span>${w.points.length-1} сегм.</span></button>`).join('');
  $('tree').innerHTML=`<div class="tree-head">▾ ${escapeText(sh.name)} · ЭЛЕМЕНТЫ</div>${symbols||'<div class="placeholder">Нет УГО</div>'}<div class="tree-head">▾ ПРОВОДНИКИ / NETS</div>${wires||'<div class="placeholder">Соединения не построены</div>'}`;
  document.querySelectorAll('[data-object]').forEach(btn=>btn.onclick=()=>{selection={type:'symbol',id:btn.dataset.object};tool='select';render();});
  document.querySelectorAll('[data-wire-object]').forEach(btn=>btn.onclick=()=>{selection={type:'wire',id:btn.dataset.wireObject};render();});
}
function renderInspector(){const sh=s(),sym=active();
  if(sym){const pinCount=LIBRARY[sym.kind].pins.length;
    $('inspector').innerHTML=`<div class="field"><label>ПОЗИЦИОННОЕ ОБОЗНАЧЕНИЕ</label><input id="field-ref" value="${escapeText(sym.ref)}"></div><div class="field"><label>НОМИНАЛ / НАИМЕНОВАНИЕ</label><input id="field-value" value="${escapeText(sym.value)}"></div><div class="field-row"><div class="field"><label>X · мм</label><input id="field-x" type="number" step="0.001" value="${mm(sym.x)}"></div><div class="field"><label>Y · мм</label><input id="field-y" type="number" step="0.001" value="${mm(sym.y)}"></div></div><div class="field"><label>УГОЛ ПОВОРОТА</label><select id="field-rotation">${[0,90,180,270].map(r=>`<option value="${r}" ${sym.rotation===r?'selected':''}>${r}°</option>`).join('')}</select></div><p class="muted">${pinCount} физических номеров выводов. Подключённые проводники перестраивают крайние колена при переносе.</p><button id="rotate-btn">↻ Повернуть 90°</button> <button id="delete-btn">Удалить</button>`;
    for(const field of ['ref','value','x','y','rotation'])$(`field-${field}`).onchange=e=>{const beforeP=before();if(field==='ref'){const val=e.target.value.trim();if(!val||sh.symbols.some(x=>x!==sym&&x.ref===val)){stateMessage('Некорректный или повторяющийся REF');render();return;}sym.ref=val;}else if(field==='value')sym.value=e.target.value;else if(field==='rotation')sym.rotation=+e.target.value;else {let v=Math.round(Number(e.target.value)*UM);if(!Number.isSafeInteger(v)){render();return;}sym[field]=v;}reanchor(sh,sym.id);commit(beforeP);};
    $('rotate-btn').onclick=()=>rotate();$('delete-btn').onclick=()=>{if(sh.wires.some(w=>[w.start.pin.symbolId,w.end.pin.symbolId].includes(sym.id))){stateMessage('Нельзя удалять символ с подключёнными проводниками');return;}const prev=before();sh.symbols=sh.symbols.filter(x=>x.id!==sym.id);selection=null;commit(prev);};
  }else if(selection?.type==='wire'){
    const w=sh.wires.find(w=>w.id===selection.id),n=sh.nets.find(n=>n.id===w?.netId);
    $('inspector').innerHTML=w?`<div class="field"><label>ЭЛЕКТРИЧЕСКАЯ СЕТЬ</label><input readonly value="${escapeText(n?.name||'—')}"></div><div class="field"><label>СЕГМЕНТОВ</label><input readonly value="${w.points.length-1}"></div><p class="muted">Перетащите внутренний сегмент проводника. Начальный и конечный отрезки защищены от отрыва PinRef.</p><button id="remove-wire">Удалить проводник</button>`:'<p class="muted">Нет данных</p>';
    if(w)$('remove-wire').onclick=()=>{const prev=before();removeWire(sh,w.id);selection=null;commit(prev);};
  }else $('inspector').innerHTML='<p class="placeholder">Выбери УГО или проводник, чтобы изменить свойства, точные координаты и ориентацию.</p>';
}
function renderDiagnostics(){let msg;try{verifyProject(project);const sh=s();msg=`<div class="status-ok">✓ Модель и привязки PinRef согласованы</div><div>Объявлено Nets: ${sh.nets.length}; проложено проводников: ${sh.wires.length}; узлов: ${sh.junctions.length}</div><div class="status-warning">⚠ Демо не подтверждено источником TL494; ERC по физическому даташиту не выполнялся.</div>`;}catch(e){msg=`<span class="status-warning">ОШИБКА: ${escapeText(e.message)}</span>`;}$('diagnostics').innerHTML=msg;}
function render(){renderCanvas();renderStructure();renderInspector();renderDiagnostics();$('project-name').value=project.title;$('dirty').textContent=dirty?'●':'';$('grid-visible').checked=gridVisible;$('grid-snap').checked=gridSnap;$('tabs').innerHTML=project.sheets.map(sh=>`<button data-sheet="${sh.id}" class="${currentSheet===sh.id?'active':''}">${escapeText(sh.name)}</button>`).join('');document.querySelectorAll('[data-sheet]').forEach(b=>b.onclick=()=>{currentSheet=b.dataset.sheet;selection=null;centerView();render();});document.querySelectorAll('[data-tool]').forEach(b=>b.classList.toggle('active',tool===b.dataset.tool));$('mode-help').textContent=placing?`Размещение: ${LIBRARY[placing].label} — щёлкните по листу`:tool==='wire'?(startPin?'Выберите конечный физический вывод; щелчок по листу добавляет колено':'Выберите физический вывод для начала цепи'):tool==='junction'?'Нажмите на пересечение проводников одной сети':'Выбор: перемещение УГО, редактирование сегмента';$('sheet-status').textContent=`${mm(s().widthUm)} × ${mm(s().heightUm)} мм`;
}
function rotate(){const sym=active();if(!sym)return;const prev=before();sym.rotation=(sym.rotation+90)%360;reanchor(s(),sym.id);commit(prev);}
function place(kind,p){const prev=before();const sh=s();const pos=snappedPoint(p);const id=uid('sym');sh.symbols.push({id,kind,ref:nextReference(sh,kind),value:kind==='ic.tl494.demo'?'TL494 · DEMO':'',x:pos.x,y:pos.y,rotation:0});selection={type:'symbol',id};placing=null;tool='select';commit(prev);stateMessage('УГО добавлено. Позиция хранится в мкм.');}
function handlePin(pin){if(!startPin){startPin=pin;waypoints=[];stateMessage(`Начало провода: ${pin.symbolId}.${pin.number}. Выберите конечный вывод.`);renderCanvas();return;}
  try{const prev=before(),w=appendWire(s(),startPin,pin,waypoints);selection={type:'wire',id:w.id};startPin=null;waypoints=[];hover=null;stateMessage('Проводник присоединён к двум физическим PinRef.');commit(prev);}catch(e){stateMessage('Соединение отклонено: '+e.message);}
}
function addJunction(at){const sh=s(),p=snappedPoint(at);const candidates=sh.wires.filter(w=>w.points.some((q,i)=>i>0&&pointOnSegment(p,w.points[i-1],q)));if(candidates.length<2){stateMessage('Нужны минимум два проводника в точке пересечения.');return;}if(new Set(candidates.map(w=>w.netId)).size!==1){stateMessage('NET_MERGE_DENIED: разные электрические сети не соединяются.');return;}if(sh.junctions.some(j=>j.x===p.x&&j.y===p.y)){stateMessage('Узел уже есть.');return;}const prev=before();sh.junctions.push({id:uid('junction'),netId:candidates[0].netId,x:p.x,y:p.y,connectedWireIds:candidates.map(w=>w.id)});commit(prev);}
canvas.addEventListener('pointerdown',e=>{
  if(e.button!==0)return;const p=worldPoint(e);if(!p)return;
  const pinEl=e.target.closest('[data-pin]'),symEl=e.target.closest('[data-symbol]'),wireEl=e.target.closest('[data-wire]');
  if(tool==='wire'){if(pinEl)handlePin({symbolId:pinEl.dataset.symbol,number:pinEl.dataset.pin});else if(startPin){waypoints.push(snappedPoint(p));stateMessage(`${waypoints.length} промежуточных точек. Укажи конечный PinRef.`);}return;}
  if(tool==='junction'){addJunction(p);return;}
  if(placing){place(placing,p);return;}
  if(tool==='select'&&symEl){const sym=s().symbols.find(x=>x.id===symEl.dataset.symbol);selection={type:'symbol',id:sym.id};drag={type:'symbol',id:sym.id,prev:before(),p,sx:sym.x,sy:sym.y};canvas.setPointerCapture(e.pointerId);render();return;}
  if(tool==='select'&&wireEl){const w=s().wires.find(w=>w.id===wireEl.dataset.wire),idx=Number(wireEl.dataset.seg);selection={type:'wire',id:w.id};if(idx===0||idx>=w.points.length-2){stateMessage('Крайние сегменты закреплены. Перетаскивай внутреннее колено.');render();return;}drag={type:'segment',id:w.id,index:idx,prev:before(),p,original:deep(w.points)};canvas.setPointerCapture(e.pointerId);render();return;}
  selection=null;render();
});
canvas.addEventListener('pointermove',e=>{
  const p=worldPoint(e);if(!p)return;$('coordinates').textContent=`X: ${mm(p.x)} / Y: ${mm(p.y)} мм`;
  if(drag){const delta={x:snappedPoint(p).x-snappedPoint(drag.p).x,y:snappedPoint(p).y-snappedPoint(drag.p).y};if(drag.type==='symbol'){
      const sym=s().symbols.find(x=>x.id===drag.id);sym.x=drag.sx+delta.x;sym.y=drag.sy+delta.y;reanchor(s(),sym.id);
    }else{const w=s().wires.find(w=>w.id===drag.id);w.points=deep(drag.original);const a=w.points[drag.index],b=w.points[drag.index+1];try{moveSegment(w,drag.index,a.x===b.x?delta.x:delta.y);}catch(err){stateMessage(err.message);}}
    renderCanvas();return;
  }
  if(startPin){hover=snappedPoint(p);renderCanvas();}
});
canvas.addEventListener('pointerup',e=>{if(!drag)return;try{canvas.releasePointerCapture(e.pointerId);}catch{}const old=drag.prev;drag=null;try{verifyProject(project);commit(old);}catch(err){project=old;stateMessage('Перемещение отклонено: '+err.message);render();}});
canvas.addEventListener('dragover',e=>e.preventDefault());canvas.addEventListener('drop',e=>{e.preventDefault();const kind=e.dataTransfer.getData('text/x-gscad-kind');const p=worldPoint(e);if(LIBRARY[kind]&&p)place(kind,p);});
canvas.addEventListener('wheel',e=>{e.preventDefault();const p=worldPoint(e);if(!p)return;const factor=e.deltaY>0?1.12:1/1.12;const w=Math.max(16000,Math.min(1200000,camera.w*factor)),h=Math.max(16000,Math.min(1200000,camera.h*factor));const px=p.x/UM,py=p.y/UM;const tx=(p.x-camera.x)/camera.w,ty=(p.y-camera.y)/camera.h;camera={x:p.x-tx*w,y:p.y-ty*h,w,h};renderCanvas();},{passive:false});
function download(name,content,mime){const url=URL.createObjectURL(new Blob([content],{type:mime})),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
const stem=()=>project.title.replace(/[^a-zA-Z0-9а-яА-ЯёЁ_-]/g,'_').slice(0,50)||'schematic';
function save(){try{download(`${stem()}.gscad.json`,serialized(project),'application/json');dirty=false;$('dirty').textContent='';stateMessage('Проект сохранён в JSON через загрузки браузера.');}catch(e){stateMessage('Сохранение не удалось: '+e.message);}}
async function savePng(){try{
  const svgText=exportSvg(project,currentSheet),sh=s(),width=Math.round(sh.widthUm/1000/25.4*300),height=Math.round(sh.heightUm/1000/25.4*300);
  const svgUrl=URL.createObjectURL(new Blob([svgText],{type:'image/svg+xml'}));const image=new Image();try{await new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=()=>reject(Error('SVG_IMAGE_LOAD'));image.src=svgUrl;});const cv=document.createElement('canvas');cv.width=width;cv.height=height;const cx=cv.getContext('2d');cx.fillStyle='#fff';cx.fillRect(0,0,width,height);cx.drawImage(image,0,0,width,height);const blob=await new Promise((r,j)=>cv.toBlob(b=>b?r(b):j(Error('CANVAS_ENCODER')),'image/png'));
    const buffer=await blob.arrayBuffer();download(`${stem()}-300dpi.png`,withPngDpi(buffer,300),'image/png');stateMessage(`PNG экспортирован: ${width}×${height} px, 300 DPI, pHYs.`);
  }finally{URL.revokeObjectURL(svgUrl);}
}catch(e){stateMessage('Ошибка PNG: '+e.message);}}
$('save-btn').onclick=save;$('svg-btn').onclick=()=>{try{download(`${stem()}.svg`,exportSvg(project,currentSheet),'image/svg+xml');stateMessage('Экспортирован чистый векторный SVG без сетки и UI.');}catch(e){stateMessage('SVG export: '+e.message);}};
$('png-btn').onclick=savePng;$('open-btn').onclick=()=>$('open-file').click();$('open-file').onchange=async e=>{const file=e.target.files?.[0];if(!file)return;try{const data=JSON.parse(await file.text());verifyProject(data);project=data;currentSheet=project.sheets[0].id;history.length=0;future.length=0;selection=null;dirty=false;centerView();render();stateMessage('Загружен проект в формате gscad-spike v1.');}catch(err){stateMessage('Открытие отклонено: '+err.message);}e.target.value='';};
$('new-btn').onclick=()=>{project=demo();currentSheet='sheet-1';history.length=0;future.length=0;selection=null;dirty=false;centerView();render();stateMessage('Создан новый демонстрационный проект.');};
$('add-sheet').onclick=()=>{const prev=before();const id=uid('sheet');project.sheets.push({id,name:`Лист ${project.sheets.length+1}`,widthUm:420000,heightUm:297000,symbols:[],nets:[],wires:[],junctions:[],graphics:[]});currentSheet=id;selection=null;commit(prev);centerView();};
$('project-name').onchange=e=>{const prev=before();project.title=e.target.value.trim()||'Без названия';commit(prev);};
$('undo').onclick=undo;$('redo').onclick=redo;$('fit').onclick=centerView;$('search').oninput=renderPalette;
$('grid-visible').onchange=e=>{gridVisible=e.target.checked;renderCanvas();};$('grid-snap').onchange=e=>{gridSnap=e.target.checked;renderCanvas();};
$('settings-btn').onclick=()=>$('settings').showModal();$('grid-step').onchange=e=>{gridStep=+e.target.value;renderCanvas();};
$('theme-btn').onclick=()=>setTheme(document.body.dataset.theme==='dark'?'light':'dark');$('theme-select').onchange=e=>setTheme(e.target.value);
document.querySelectorAll('[data-tool]').forEach(btn=>btn.onclick=()=>setTool(btn.dataset.tool));
window.addEventListener('keydown',e=>{
  const editing=['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName);if(e.key==='Escape'){placing=null;startPin=null;waypoints=[];hover=null;drag=null;tool='select';render();return;}
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();save();return;}
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();e.shiftKey?redo():undo();return;}
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='y'){e.preventDefault();redo();return;}
  if(editing)return;if(e.key.toLowerCase()==='v')setTool('select');if(e.key.toLowerCase()==='w')setTool('wire');if(e.key.toLowerCase()==='j')setTool('junction');if(e.key.toLowerCase()==='r')rotate();
});
// Simple desktop dock resize; dimensions are UI preferences, never electrical geometry.
const root=$('app');
for(const [side,handleId,fallback] of [['left','left-split',258],['right','right-split',276]]){
  const stored=Number(localStorage.getItem(`gscad-r0-${side}-width`));
  const initial=Number.isFinite(stored)&&stored>120?stored:fallback;
  root.style.setProperty(`--${side}-width`,`${initial}px`);
  const handle=$(handleId);let activePointer=null;
  handle.addEventListener('pointerdown',e=>{activePointer=e.pointerId;handle.setPointerCapture(e.pointerId);e.preventDefault();});
  handle.addEventListener('pointermove',e=>{if(activePointer!==e.pointerId)return;const vw=window.innerWidth;const max=Math.max(180,vw-580);let width=side==='left'?e.clientX:vw-e.clientX;width=Math.max(side==='left'?175:225,Math.min(max,width));root.style.setProperty(`--${side}-width`,`${Math.round(width)}px`);});
  handle.addEventListener('pointerup',e=>{if(activePointer!==e.pointerId)return;activePointer=null;try{handle.releasePointerCapture(e.pointerId);}catch{}const value=getComputedStyle(root).getPropertyValue(`--${side}-width`).trim();localStorage.setItem(`gscad-r0-${side}-width`,String(parseInt(value,10)));});
  handle.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();const current=parseInt(getComputedStyle(root).getPropertyValue(`--${side}-width`),10),step=e.shiftKey?25:10,inc=(e.key==='ArrowRight'?1:-1)*(side==='right'?-1:1);const next=Math.max(side==='left'?175:225,current+inc*step);root.style.setProperty(`--${side}-width`,`${next}px`);localStorage.setItem(`gscad-r0-${side}-width`,String(next));});
}
// Crash recovery never bypasses schema validation or auto-merges with source-locked projects.
try {
  const restored=localStorage.getItem('gscad-r0-recovery');
  if(restored){const parsed=JSON.parse(restored);verifyProject(parsed);
    if(window.confirm('Обнаружено автосохранение CAD R0. Восстановить проект?')){project=parsed;currentSheet=project.sheets[0].id;dirty=true;stateMessage('Восстановлена незавершённая сессия R0.');}
  }
} catch(e){stateMessage('Автовосстановление отклонено: '+e.message);}
setTheme(localStorage.getItem('gscad-r0-theme')||'dark');renderPalette();requestAnimationFrame(()=>{centerView();render();});
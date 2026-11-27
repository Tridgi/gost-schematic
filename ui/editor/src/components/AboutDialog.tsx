import {useEffect,useRef,useState} from 'react';
import {Alert,Button,Divider,Group,Modal,Progress,Stack,Switch,Text} from '@mantine/core';
import {useLocalStorage} from '@mantine/hooks';
import {nativeDesktopAvailable,nativeAppVersion,nativeOpenProjectLink,type ProjectLink,nativeSignedUpdateEnabled,nativeSignedUpdateStatus,nativePrepareSignedUpdate,nativeCancelSignedDownload,nativeDiscardSignedUpdate,nativeInstallSignedUpdate,type SignedUpdateStatus} from '../native/desktop';
import {checkLatestRelease,type ReleaseStatus} from '../native/release-check';
import pkg from '../../package.json';

const urls:Record<ProjectLink,string>={
  founder:'https://github.com/Tridgi',
  repository:'https://github.com/Tridgi/gost-schematic',
  releases:'https://github.com/Tridgi/gost-schematic/releases'
};
type State=ReleaseStatus|{kind:'idle'|'checking'|'error'};
export function AboutDialog({opened,onClose,onAvailable,canInstallUpdate}:{opened:boolean;onClose:()=>void;onAvailable:(version:string|null)=>void;canInstallUpdate?:()=>boolean}){
  const native=nativeDesktopAvailable();
  const [version,setVersion]=useState(native?'':pkg.version);
  const [state,setState]=useState<State>({kind:'idle'});
  const [linkError,setLinkError]=useState(false);
  const [signedEnabled,setSignedEnabled]=useState(false);
  const [signed,setSigned]=useState<SignedUpdateStatus>({kind:'idle'});
  const [signedError,setSignedError]=useState('');
  const [installing,setInstalling]=useState(false);
  const operation=useRef(false);
  useEffect(()=>{
    let active=true;
    if(native)nativeSignedUpdateEnabled().then(v=>{if(active)setSignedEnabled(v===true);}).catch(()=>{});
    return()=>{active=false;};
  },[native]);
  useEffect(()=>{
    if(!native||!signedEnabled)return;
    let active=true;
    async function refresh(){try{const next=await nativeSignedUpdateStatus();if(active)setSigned(next);}catch{}}
    void refresh();
    const timer=setInterval(()=>void refresh(),500);
    return()=>{active=false;clearInterval(timer);};
  },[native,signedEnabled]);
  async function prepareUpdate(rawVersion:string){
    if(operation.current||!signedEnabled)return;
    operation.current=true;setSignedError('');
    try{
      setSigned({kind:'downloading',received:0,total:null});
      await nativePrepareSignedUpdate(rawVersion.replace(/^v/,''));
      setSigned(await nativeSignedUpdateStatus());
    }catch(error){setSigned({kind:'idle'});setSignedError(String(error).includes('UPDATE_DOWNLOAD_CANCELLED')?'Загрузка отменена. Установка не выполнялась.':'Не удалось скачать или проверить подпись обновления. Установка не выполнялась.');}
    finally{operation.current=false;}
  }
  async function cancelDownload(){
    if(signed.kind!=='downloading'||!signed.id||signed.cancelling)return;
    const id=signed.id;
    setSignedError('');
    try{await nativeCancelSignedDownload(id);setSigned(await nativeSignedUpdateStatus());}
    catch{setSignedError('Не удалось отменить загрузку: операция уже завершилась или изменилась.');}
  }
  async function discardUpdate(){
    if(operation.current)return;
    operation.current=true;setSignedError('');
    try{await nativeDiscardSignedUpdate();setSigned({kind:'idle'});}
    catch{setSignedError('Не удалось отменить подготовленное обновление.');}
    finally{operation.current=false;}
  }
  async function installUpdate(){
    if(operation.current||signed.kind!=='ready'||!signedEnabled)return;
    if(!canInstallUpdate?.()){setSignedError('Сначала сохраните проект и завершите текущую операцию.');return;}
    if(!window.confirm('Установить проверенное обновление '+signed.version+' и перезапустить СХЕМАТИК?'))return;
    if(!canInstallUpdate?.()){setSignedError('Состояние проекта изменилось. Сохраните его перед установкой.');return;}
    operation.current=true;setInstalling(true);setSignedError('');
    try{await nativeInstallSignedUpdate(signed.token,true);}
    catch{setSignedError('Установка не запущена: завершите файловые операции или повторите загрузку.');}
    finally{operation.current=false;setInstalling(false);try{setSigned(await nativeSignedUpdateStatus());}catch{}}
  }
  const [showLicense,setShowLicense]=useState(false);
  const [auto,setAuto]=useLocalStorage({key:'gscad.checkUpdatesOnStart',defaultValue:false});
  const request=useRef<AbortController|null>(null);
  const checkedAtStart=useRef(false);
  useEffect(()=>{
    let active=true;
    if(native)nativeAppVersion().then(v=>{if(typeof v!=='string'||!v.trim())throw Error('INVALID_NATIVE_VERSION');if(active)setVersion(v);}).catch(()=>{if(active)setState({kind:'error'});});
    return()=>{active=false;};
  },[native]);
  useEffect(()=>()=>request.current?.abort(),[]);
  async function check(){
    if(!native||!version||request.current)return;
    const controller=new AbortController();request.current=controller;
    setState({kind:'checking'});
    const timer=setTimeout(()=>controller.abort(),10000);
    try{const result=await checkLatestRelease(version,controller.signal);setState(result);onAvailable(result.kind==='available'?result.version??null:null);}
    catch{if(request.current===controller){setState({kind:'error'});onAvailable(null);}}
    finally{clearTimeout(timer);if(request.current===controller)request.current=null;}
  }
  useEffect(()=>{
    if(native&&version&&auto&&!checkedAtStart.current){checkedAtStart.current=true;void check();}
  },[native,version,auto]);
  async function openLink(link:ProjectLink){
    setLinkError(false);
    try{if(native)await nativeOpenProjectLink(link);else window.open(urls[link],'_blank','noopener,noreferrer');}
    catch{setLinkError(true);}
  }
  return <Modal opened={opened} onClose={()=>{if(!installing)onClose();}} closeOnEscape={!installing} closeOnClickOutside={!installing} withCloseButton={!installing} title="О программе" centered size="md" data-testid="about-dialog">
    <Stack gap="sm">
      <Text fw={700} size="xl">СХЕМАТИК</Text>
      <Text size="sm">GOST Schematic Engine — редактор электрических схем</Text>
      <Text size="sm" data-testid="about-version">Версия: {version||'не удалось определить'}{native?'':' (браузерная сборка)'}</Text>
      <Text size="sm">© 2026. Основатель и первоначальный разработчик — Мирослав Лихачёв (Tridgi). При участии контрибьюторов проекта.</Text>
      <Group gap="xs">
        <Button size="xs" variant="light" onClick={()=>void openLink('founder')}>Автор на GitHub</Button>
        <Button size="xs" variant="light" onClick={()=>void openLink('repository')}>Репозиторий</Button>
      </Group>
      {linkError&&<Alert color="yellow">Не удалось открыть системный браузер.</Alert>}
      <Button size="xs" variant="subtle" onClick={()=>setShowLicense(v=>!v)}>{showLicense?'Скрыть':'Показать'} MIT License</Button>
      {showLicense&&<Text size="xs" style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{MIT_LICENSE}</Text>}
      <Divider label="Обновления" labelPosition="left"/>
      <Switch label="Проверять обновления при запуске" checked={auto} disabled={!native} onChange={event=>setAuto(event.currentTarget.checked)}/>
      <Text size="xs" c="dimmed">Проверка обращается к публичному GitHub Releases без учётных данных. {signedEnabled?'Подписанные обновления доступны.':'В этой сборке ключ подписи обновлений не настроен; используйте страницу релизов.'}</Text>
      {state.kind==='available'&&<Alert color="blue" data-testid="update-result">Доступна версия {state.version}. {signedEnabled?'Можно скачать проверяемый пакет.':'Откройте страницу релизов для получения обновления.'}</Alert>}
      {state.kind==='current'&&<Text size="sm" data-testid="update-result">Более новой стабильной версии нет.</Text>}
      {state.kind==='none'&&<Text size="sm" data-testid="update-result">Публичный стабильный релиз не найден или недоступен.</Text>}
      {state.kind==='error'&&<Alert color="yellow" data-testid="update-result">Не удалось проверить версию. Проверьте подключение к GitHub и повторите попытку.</Alert>}
      {!native&&<Text size="xs" c="dimmed">Проверка обновлений доступна в установленном приложении.</Text>}
      <Group gap="xs">
        <Button size="xs" data-testid="check-updates" loading={state.kind==='checking'} disabled={!native||!version} onClick={()=>void check()}>Проверить обновления</Button>
        <Button size="xs" variant="default" onClick={()=>void openLink('releases')}>Все релизы GitHub</Button>
      </Group>
      {signedEnabled&&state.kind==='available'&&state.version&&signed.kind==='idle'&&<Button data-testid="download-signed-update" onClick={()=>void prepareUpdate(state.version!)}>Скачать и проверить обновление</Button>}
      {signedEnabled&&signed.kind==='downloading'&&<Stack gap={4}>
        <Text size="sm">Получено {(signed.received/1048576).toFixed(1)} МБ{signed.total?' из '+(signed.total/1048576).toFixed(1)+' МБ':''}</Text>
        <Progress animated={!signed.cancelling} value={signed.total?Math.min(100,signed.received/signed.total*100):0}/>
        <Button data-testid="cancel-signed-download" variant="default" disabled={!signed.id||signed.cancelling} onClick={()=>void cancelDownload()}>{signed.cancelling?'Отмена…':'Отменить загрузку'}</Button>
        <Text size="xs" c="dimmed">После загрузки будет проверена цифровая подпись. Установка не начнётся автоматически.</Text>
      </Stack>}
      {signedEnabled&&signed.kind==='ready'&&<Stack gap="xs">
        <Alert color="green">Пакет версии {signed.version} скачан, подпись проверена.</Alert>
        <Button data-testid="install-signed-update" loading={installing} onClick={()=>void installUpdate()}>Установить и перезапустить</Button>
        <Button variant="default" disabled={installing} onClick={()=>void discardUpdate()}>Удалить скачанный пакет</Button>
      </Stack>}
      {signedError&&<Alert color="yellow" data-testid="signed-update-error">{signedError}</Alert>}
      <Button variant="default" disabled={installing} onClick={onClose}>Закрыть</Button>
    </Stack>
  </Modal>;
}
const MIT_LICENSE=`MIT License

Copyright (c) 2026 GOST Schematic Engine contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.`;

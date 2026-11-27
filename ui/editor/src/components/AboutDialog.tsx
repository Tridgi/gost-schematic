import {useEffect,useRef,useState} from 'react';
import {Alert,Button,Divider,Group,Modal,Stack,Switch,Text} from '@mantine/core';
import {useLocalStorage} from '@mantine/hooks';
import {nativeDesktopAvailable,nativeAppVersion,nativeOpenProjectLink,type ProjectLink} from '../native/desktop';
import {checkLatestRelease,type ReleaseStatus} from '../native/release-check';
import pkg from '../../package.json';

const urls:Record<ProjectLink,string>={
  founder:'https://github.com/Tridgi',
  repository:'https://github.com/Tridgi/gost-schematic',
  releases:'https://github.com/Tridgi/gost-schematic/releases'
};
type State=ReleaseStatus|{kind:'idle'|'checking'|'error'};
export function AboutDialog({opened,onClose}:{opened:boolean;onClose:()=>void}){
  const native=nativeDesktopAvailable();
  const [version,setVersion]=useState(native?'':pkg.version);
  const [state,setState]=useState<State>({kind:'idle'});
  const [linkError,setLinkError]=useState(false);
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
    try{setState(await checkLatestRelease(version,controller.signal));}
    catch{if(request.current===controller)setState({kind:'error'});}
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
  return <Modal opened={opened} onClose={onClose} title="О программе" centered size="md" data-testid="about-dialog">
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
      <Text size="xs" c="dimmed">Проверка обращается к публичному GitHub Releases без учётных данных. Установка подписанных обновлений пока не подключена.</Text>
      {state.kind==='available'&&<Alert color="blue" data-testid="update-result">Доступна версия {state.version}. Откройте страницу релизов для получения обновления.</Alert>}
      {state.kind==='current'&&<Text size="sm" data-testid="update-result">Более новой стабильной версии нет.</Text>}
      {state.kind==='none'&&<Text size="sm" data-testid="update-result">Публичный стабильный релиз не найден или недоступен.</Text>}
      {state.kind==='error'&&<Alert color="yellow" data-testid="update-result">Не удалось проверить версию. Проверьте подключение к GitHub и повторите попытку.</Alert>}
      {!native&&<Text size="xs" c="dimmed">Проверка обновлений доступна в установленном приложении.</Text>}
      <Group gap="xs">
        <Button size="xs" data-testid="check-updates" loading={state.kind==='checking'} disabled={!native||!version} onClick={()=>void check()}>Проверить обновления</Button>
        <Button size="xs" variant="default" onClick={()=>void openLink('releases')}>Все релизы GitHub</Button>
      </Group>
      <Button variant="default" onClick={onClose}>Закрыть</Button>
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

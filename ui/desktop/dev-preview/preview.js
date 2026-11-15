const out = document.getElementById('result');
const id = () => 'req_' + Date.now().toString(36);
let current = null;
document.getElementById('hello').addEventListener('click', async () => {
  current = id();
  try {
    const result = await window.__TAURI__.core.invoke('engine_request', {
      request: { v: 1, id: current, op: 'hello', args: {} }
    });
    out.textContent = JSON.stringify(result, null, 2);
  } catch (error) { out.textContent = String(error); }
  finally { current = null; }
});
document.getElementById('cancel').addEventListener('click', async () => {
  if (!current) { out.textContent = 'Активного запроса нет'; return; }
  const result = await window.__TAURI__.core.invoke('cancel_engine_request', { id: current });
  out.textContent = result ? 'Процесс отменён' : 'Процесс уже завершён';
});

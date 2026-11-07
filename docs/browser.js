"use strict";
(() => {
  let worker, sequence = 0, currentCase = null, currentData = null;
  let ollama = {ollama_available:false, ollama_model:'qwen3:4b', ollama_message:'Opcional: conecta Ollama en este equipo. El análisis y el PDF funcionan sin él.'};
  const pending = new Map();
  const response = value => new Response(JSON.stringify(value), {headers:{'Content-Type':'application/json'}});
  function workerCall(action, data = {}) {
    if (!worker) {
      worker = new Worker('./browser-worker.js?v=ccc9e18b37d3');
      worker.onmessage = ({data:message}) => {
        if (message.progress) { document.querySelector('#loading p').textContent = message.progress; return; }
        const job = pending.get(message.id);
        if (!job) return;
        pending.delete(message.id);
        if (message.initFailed) { worker.terminate(); worker = null; }
        if (message.error) job.reject(new Error(message.error)); else job.resolve(message.result);
      };
      worker.onerror = () => {
        for (const job of pending.values()) job.reject(new Error('El motor del navegador no pudo continuar. Recarga la página y prueba con un archivo más pequeño.'));
        pending.clear(); worker.terminate(); worker = null;
      };
    }
    return new Promise((resolve, reject) => {
      const id = ++sequence; pending.set(id,{resolve,reject});
      worker.postMessage({id,action,data}, data.bytes ? [data.bytes] : []);
    });
  }
  async function localOllama(path, options = {}) {
    let res;
    try {
      res = await fetch('http://127.0.0.1:11434/api/' + path, {...options, signal:AbortSignal.timeout(path === 'chat' ? 180000 : 5000)});
    } catch {
      ollama.ollama_available = false;
      ollama.ollama_message = 'No se pudo conectar con Ollama. Inícialo, autoriza esta página en OLLAMA_ORIGINS y permite el acceso a la red local si tu navegador lo solicita. Consulta la guía de conexión.';
      window.dispatchEvent(new CustomEvent('soc-ollama-status',{detail:ollama}));
      throw new Error(ollama.ollama_message);
    }
    if (!res.ok) throw new Error(`Ollama respondió con un error (${res.status}). Comprueba que el modelo esté instalado y consulta la guía de conexión.`);
    return res;
  }
  window.socBrowser = {
    async api(url, options = {}) {
      if (url === '/api/health') return response({status:'ok',...ollama});
      if (url === '/api/default') {
        const res = await fetch('./data/default-case.json?v=3061760e723c', {cache:'no-store'});
        if (!res.ok) throw new Error('No se pudo abrir el Excel del proyecto. Puedes seleccionar otro Excel.');
        currentData = await res.json();
        currentCase = currentData.id;
        return response(currentData);
      }
      if (url === '/api/analyze') {
        const file = options.body.get('file');
        const caseId = crypto.randomUUID();
        const offset = options.body.get('timezone_offset');
        const result = await workerCall('analyze',{bytes:await file.arrayBuffer(),filename:file.name,offset:offset === null ? null : Number(offset),caseId});
        currentCase = caseId;
        currentData = result;
        return response(result);
      }
      const match = url.match(/^\/api\/cases\/([^/]+)(?:\/(report\.pdf|evidence\.json|assistant))?$/);
      if (!match) throw new Error('Operación no admitida en la edición de navegador.');
      // Upload replaces the worker's case. Cleanup of the previous ID must not erase it.
      if (options.method === 'DELETE') {
        if (match[1] === currentCase) { if (worker) await workerCall('delete'); currentCase = null; currentData = null; }
        return response({deleted:true});
      }
      if (!currentCase || match[1] !== currentCase) throw new Error('Carga de nuevo el Excel para continuar.');
      currentData.metadata.case_context = Object.fromEntries(['analyst','client','company','reference'].map(key => [key, document.querySelector(`#case-${key}`).value.trim()]));
      if (match[2] === 'evidence.json') return response(currentData);
      if (match[2] === 'report.pdf') {
        await workerCall('restore',{case:currentData});
        return new Response(await workerCall('pdf'), {headers:{'Content-Type':'application/pdf'}});
      }
      if (match[2] === 'assistant') {
        if (!ollama.ollama_available) throw new Error('Conecta primero Ollama en este equipo.');
        await workerCall('restore',{case:currentData});
        const request = await workerCall('request',{model:ollama.ollama_model});
        const res = await localOllama('chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
        const text = await res.text();
        if (text.length > 100000) throw new Error('La respuesta IA excede el tamaño permitido.');
        let payload;
        try { payload = JSON.parse(JSON.parse(text).message.content); }
        catch { throw new Error('Ollama no devolvió una selección válida. El informe anterior se conserva.'); }
        currentData.narrative = await workerCall('selection',{payload,model:ollama.ollama_model});
        return response(currentData.narrative);
      }
      throw new Error('Operación no admitida.');
    }
  };
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelector('#connect-ollama').addEventListener('click',async event => {
      const button = event.currentTarget; button.disabled=true;
      const status = document.querySelector('#ollama-connection-status');
      status.textContent='Comprobando Ollama en este equipo…';
      try {
        const model = document.querySelector('#ollama-model').value.trim();
        if (!/^[a-zA-Z0-9_.:/-]{1,120}$/.test(model)) throw new Error('Indica un nombre de modelo válido.');
        const tags = await (await localOllama('tags')).json();
        if (!tags.models?.some(m=>m.name === model || m.name === model+':latest')) throw new Error(`Descarga primero el modelo ${model} en Ollama.`);
        ollama = {ollama_available:true,ollama_model:model,ollama_message:`${model} conectado en este equipo.`};
        status.textContent=ollama.ollama_message;
      } catch(error) {
        ollama.ollama_available=false; ollama.ollama_message=error.message;
        status.textContent=error.message;
      } finally {
        button.disabled=false;
        window.dispatchEvent(new CustomEvent('soc-ollama-status',{detail:ollama}));
      }
    });
  });
})();

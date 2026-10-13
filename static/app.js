'use strict';
const $ = s => document.querySelector(s);
let mode = 'create', uploading = false, paused = false, latest = {jobs:[],uploads:[]}, poll;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path, method='GET', body) {
  const options = {method, headers:{'X-Watermark-Request':'1'}};
  if (body !== undefined) { options.body=JSON.stringify(body); options.headers['Content-Type']='application/json'; }
  const response = await fetch('/api'+path,options);
  const data = await response.json();
  if (!response.ok) {
    if(response.status===401 && path!=='/login') lock();
    throw new Error(typeof data.detail==='string'?data.detail:'Please check the entered values.');
  }
  return data;
}
function lock(){clearTimeout(poll);$('#workspace').hidden=true;$('#login-view').hidden=false;$('#logout').hidden=true;}
function unlock(){$('#workspace').hidden=false;$('#login-view').hidden=true;$('#logout').hidden=false;refresh();}
$('#login-form').addEventListener('submit',async e=>{e.preventDefault();$('#login-error').textContent='';try{await api('/login','POST',{password:$('#password').value});$('#password').value='';unlock();}catch(e){$('#login-error').textContent=e.message;}});
$('#logout').onclick=async()=>{await api('/logout','POST',{});lock();};
function switchMode(next){mode=next;for(const m of ['create','check']){const selected=m===mode;$('#'+m+'-tab').classList.toggle('active',selected);selected?$('#'+m+'-tab').setAttribute('aria-current','page'):$('#'+m+'-tab').removeAttribute('aria-current');$('#'+m+'-options').hidden=!selected;$('#'+m+'-options').querySelectorAll('input,select').forEach(x=>x.disabled=!selected);}
  $('#setup-heading').textContent=mode==='create'?'Choose your video':'Choose the suspected leak';$('#submit-job').textContent=mode==='create'?'Create watermarked copies':'Check this window';$('#form-error').textContent='';updateStorageBudget();}
$('#create-tab').onclick=()=>switchMode('create');$('#check-tab').onclick=()=>switchMode('check');switchMode('create');
$('#batch-label').oninput=()=>{$('#batch-label').nextElementSibling.textContent=`Files will be named ${$('#batch-label').value||'Copy'} 001, ${$('#batch-label').value||'Copy'} 002, and so on.`;};
function fillSelect(id,kind){const el=$(id),before=el.value;const items=latest.uploads.filter(x=>x.kind===kind&&x.complete);el.innerHTML='<option value="">Choose an uploaded '+(kind==='video'?'video':'recovery file')+'</option>'+items.map(x=>`<option value="${x.id}">${esc(x.name)}</option>`).join('');if(items.some(x=>x.id===before))el.value=before;}
function updateStorageBudget(){
  const hint=$('#storage-budget'),storage=latest.storage,copies=Number($('#copies').value),limit=Number($('#max-gb').value);
  let insufficient=false;
  if(storage&&Number.isInteger(copies)&&copies>=1&&copies<=100&&Number.isFinite(limit)&&limit>=.01&&limit<=100){
    const perCopy=Math.ceil(limit*1e9),needed=perCopy*(1+storage.temporary_copies)+storage.reserve_bytes;
    const fullBatch=perCopy*(copies+storage.temporary_copies)+storage.reserve_bytes;
    insufficient=storage.free_bytes<needed;
    hint.textContent=`${(storage.free_bytes/1e9).toFixed(2)} GB free · ${(needed/1e9).toFixed(2)} GB needed for the next copy. `+
      (insufficient?'Free space or use a larger storage volume before starting. ':`Copies are made one at a time. Up to ${(fullBatch/1e9).toFixed(2)} GB would be needed if every copy reached its size limit; actual files may be much smaller. `)+
      'If storage gets low, processing stops and finished copies and the recovery file remain available to download.';
  }else hint.textContent=storage?'Enter a valid copy count and size limit to see the storage check.':'Checking available storage…';
  hint.classList.toggle('error',insufficient);
  $('#submit-job').disabled=Boolean(latest.busy||uploading||(mode==='create'&&insufficient));
}
$('#copies').addEventListener('input',updateStorageBudget);$('#max-gb').addEventListener('input',updateStorageBudget);
async function refresh(){clearTimeout(poll);try{latest=await api('/state');$('#storage').textContent=latest.free_gb+' GB free';fillSelect('#video-select','video');fillSelect('#recovery-select','recovery');renderJobs();updateStorageBudget();$('#busy-note').textContent=latest.busy?'A job is running. Wait for it to finish or stop it below.':'One job runs at a time. You can close this tab while the Pod keeps running.';renderUploads();}catch(e){$('#form-error').textContent=e.message;}if(!$('#workspace').hidden)poll=setTimeout(refresh,2500);}
function renderJobs(){const signature=JSON.stringify(latest.jobs);if($('#jobs').dataset.signature===signature)return;$('#jobs').dataset.signature=signature;$('#empty').hidden=latest.jobs.length>0;$('#job-count').textContent=latest.jobs.length;
  $('#jobs').innerHTML=latest.jobs.map(j=>{let result='';if(j.status==='complete'&&j.kind==='check'){const success=j.result?.status==='registered_copy_recovered';result=`<div class="result">${success?'Recovered copy: <strong>'+esc(j.result.aggregate.copy_label)+'</strong>':'Inconclusive. No reliable copy ID recovered.'}<p class="hint">${success?'The aggregate and both halves recovered the same authenticated ID.':'This does not prove that a watermark is absent. Try a different or longer window.'}</p></div>`;}
  const progress=j.status==='running'&&j.total_frames>0?`<progress max="${j.total_frames}" value="${Math.min(j.frames,j.total_frames)}" aria-label="Video processing progress"></progress>`:'';
  return `<article class="job" data-job="${j.id}"><div class="job-top"><h3>${esc(j.title)}</h3><span class="status ${j.status}">${esc(j.status)}</span></div><p class="job-source">${esc(j.source)}</p><p class="phase">${esc(j.phase)}${j.total?' · '+(j.copy||0)+' / '+j.total:''}</p>${progress}${j.error?'<p class="error">'+esc(j.error)+'</p>':''}${result}<div>${j.files.map(f=>`<div class="file-row"><a href="/api/jobs/${j.id}/files/${encodeURIComponent(f.name)}" download>${esc(f.label)}</a><span class="${f.kind==='private'?'private':''}">${f.kind==='private'?'KEEP PRIVATE':f.kind==='video'?'MP4':'JSON'}</span></div>`).join('')}</div><div class="job-actions"><button class="quiet" data-action="${j.status==='running'?'cancel':'remove'}" data-id="${j.id}">${j.status==='running'?'Stop processing':'Remove batch'}</button></div></article>`;}).join('');}
$('#jobs').onclick=async e=>{const b=e.target.closest('button[data-action]');if(!b)return;const id=b.dataset.id;if(b.dataset.action==='cancel'){b.disabled=true;try{await api('/jobs/'+id+'/cancel','POST',{});b.textContent='Stopping…';}catch(e){$('#form-error').textContent=e.message;}return;}confirmRemoval(b,'Delete this batch and its private recovery file?',async()=>{await api('/jobs/'+id,'DELETE',{});await refresh();});};
function confirmRemoval(button,message,action){if(button.parentElement.querySelector('.delete-confirm'))return;const box=document.createElement('div');box.className='delete-confirm';box.innerHTML=`<span>${esc(message)}</span><button type="button">Delete</button><button type="button">Keep</button>`;button.parentElement.append(box);box.querySelectorAll('button')[1].onclick=()=>box.remove();box.querySelector('button').onclick=async()=>{try{await action();box.remove();}catch(e){$('#form-error').textContent=e.message;}};}
function renderUploads(){const host=$('#uploads-list');const signature=JSON.stringify(latest.uploads);if(host.dataset.signature===signature)return;host.dataset.signature=signature;host.innerHTML=latest.uploads.map(u=>`<div class="file-row"><span>${esc(u.name)}${u.complete?'':' (unfinished upload)'}</span><button class="quiet" data-id="${u.id}">Remove</button></div>`).join('');}
$('#uploads-list').onclick=e=>{const b=e.target.closest('button');if(b)confirmRemoval(b,'Delete this upload?',async()=>{await api('/uploads/'+b.dataset.id,'DELETE',{});await refresh();});};
async function fingerprint(file){const bytes=await new Blob([file.slice(0,1048576),file.slice(Math.max(0,file.size-1048576))]).arrayBuffer();const hash=await crypto.subtle.digest('SHA-256',bytes);return file.name+':'+file.size+':'+file.lastModified+':'+Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('');}
async function upload(file,kind){if(!file||uploading)return;uploading=true;paused=false;$('#form-error').textContent='';$('#upload-progress').hidden=false;$('#pause-upload').disabled=false;$('#submit-job').disabled=true;
  try{const key='wm-upload:'+await fingerprint(file);let id=sessionStorage.getItem(key),offset=0;
    if(id){let info;try{info=await api('/uploads/'+id);}catch{ id=null;}if(info){$('#upload-text').textContent='Checking the saved part before resuming…';for(const chunk of info.chunks){const data=await file.slice(chunk.offset,chunk.offset+chunk.size).arrayBuffer();const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data)),b=>b.toString(16).padStart(2,'0')).join('');if(digest!==chunk.sha256)throw new Error('The saved part belongs to different file contents. Remove the unfinished upload before trying again.');}offset=info.offset;}}
    if(!id){const created=await api('/uploads','POST',{name:file.name,size:file.size,kind});id=created.id;sessionStorage.setItem(key,id);}
    while(offset<file.size){if(paused)throw new Error('Upload paused. Choose the same file again to resume in this tab.');const end=Math.min(offset+8*1024*1024,file.size);$('#upload-text').textContent=`Uploading ${file.name} · ${Math.floor(offset/file.size*100)}%`;$('#upload-bar').value=offset/file.size*100;
      const response=await fetch('/api/uploads/'+id+'/chunks',{method:'PUT',headers:{'X-Watermark-Request':'1','X-Upload-Offset':String(offset)},body:file.slice(offset,end)});const data=await response.json();if(!response.ok)throw new Error(data.detail||'Upload interrupted. Choose the same file to resume.');offset=data.offset;}
    $('#upload-text').textContent='Checking uploaded file…';$('#upload-bar').value=100;await api('/uploads/'+id+'/finish','POST',{});sessionStorage.removeItem(key);await refresh();$(kind==='video'?'#video-select':'#recovery-select').value=id;$('#upload-progress').hidden=true;
  }catch(e){$('#form-error').textContent=e.message;}finally{uploading=false;updateStorageBudget();$('#pause-upload').disabled=true;$('#video-file').value='';$('#recovery-file').value='';}}
$('#video-file').onchange=e=>upload(e.target.files[0],'video');$('#recovery-file').onchange=e=>upload(e.target.files[0],'recovery');$('#pause-upload').onclick=()=>{paused=true;$('#pause-upload').disabled=true;};
const drop=$('#video-drop');drop.ondragover=e=>{e.preventDefault();drop.classList.add('drag');};drop.ondragleave=()=>drop.classList.remove('drag');drop.ondrop=e=>{e.preventDefault();drop.classList.remove('drag');if(e.dataTransfer.files.length!==1){$('#form-error').textContent='Choose one video at a time.';return;}upload(e.dataTransfer.files[0],'video');};
$('#job-form').onsubmit=async e=>{e.preventDefault();$('#form-error').textContent='';$('#submit-job').disabled=true;try{const body={kind:mode==='create'?'create':'check',video:$('#video-select').value};if(mode==='create')Object.assign(body,{copies:Number($('#copies').value),label:$('#batch-label').value,max_gb:Number($('#max-gb').value)});else Object.assign(body,{recovery:$('#recovery-select').value,start:Number($('#start').value),seconds:Number($('#seconds').value)});await api('/jobs','POST',body);await refresh();}catch(e){$('#form-error').textContent=e.message;updateStorageBudget();}};
api('/session').then(s=>s.authenticated?unlock():lock()).catch(()=>{$('#login-error').textContent='Cannot reach the app. Check that the Pod is running.';});

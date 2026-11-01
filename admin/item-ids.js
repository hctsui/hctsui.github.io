/* Item ID database: explicit, reviewable, typed rename operations. */
(function installItemIdDatabase(){
  'use strict';
  const selector='#itemIdsPane';
  let query='',kind='';
  const byId=id=>document.getElementById(id);
  const html=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pretty=item=>{
    const source=item?.title || item?.course || item?.organization || {};
    return typeof source==='string'?source:String(source.en||source.zh||item?.personal_key||item?.id||'');
  };
  const all=()=>typeof site!=='undefined'&&site ?
    ['activities','honors','publications','teaching','profile_items'].flatMap(k=>site[k]||[]):[];
  function pendingFor(old){return typeof draft!=='undefined'?draft.find(o=>o.op==='rename_id'&&o.id===old):null;}
  function filterRow(item){
    if(kind&&item.type!==kind)return false;
    if(!query)return true;
    const str=[item.id,item.type,pretty(item),item?.term?.en,item?.start_date,item?.date].filter(Boolean).join(' ').toLowerCase();
    return str.includes(query);
  }
  function render(){
    const root=byId('itemIdRecords');if(!root)return;
    // The main CMS loads site.json asynchronously after this script starts.
    const types=byId('itemIdType');
    if(types){
      const options=[...new Set(all().map(x=>x.type))].sort();
      const signature=options.join('|');
      if(types.dataset.signature!==signature){
        types.dataset.signature=signature;
        types.innerHTML='<option value="">全部</option>'+options.map(t=>`<option value="${html(t)}">${html(t)}</option>`).join('');
        types.value=kind;
      }
    }
    const rows=all().filter(filterRow);
    root.innerHTML=rows.map(item=>{
      const pending=pendingFor(item.id),current=pending?.new_id||item.id;
      return `<div class="row item-id-row" data-item-original-id="${html(item.id)}">
        <span class="tag">${html(item.type)}</span>
        <div class="record-heading"><strong>${html(pretty(item))}</strong><span class="muted record-meta">${html(item?.term?.en||item.start_date||item.date||item.year||'')}</span></div>
        <div class="id">${html(item.id)}</div>
        <div class="field" style="min-width:min(290px,100%)"><label>新 ID</label><input data-proposed-id="${html(item.id)}" value="${html(current)}" spellcheck="false" autocomplete="off" aria-label="${html(item.id)} 的新 ID" /></div>
        <div class="actions"><button type="button" class="button" data-stage-id="${html(item.id)}">${pending?'更新草稿':'更改 ID'}</button>${pending?`<button type="button" class="button danger" data-revert-id="${html(item.id)}">取消改名</button>`:''}</div>
      </div>`;
    }).join('')||'<p class="muted">沒有符合的項目。</p>';
  }
  window.renderItemIds=render;
  function stage(old,newId){
    if(typeof site==='undefined'||!site)return;
    const item=all().find(x=>x.id===old);
    if(!item)return flash('找不到原項目，請重新整理後台');
    if(!new RegExp(`^${item.type}-[a-z0-9]+(?:-[a-z0-9]+)*$`).test(newId))return flash('ID 必須以 '+item.type+'- 開頭，且僅能使用小寫英文、數字與連字號');
    if(newId===old){
      draft=draft.filter(x=>!(x.op==='rename_id'&&x.id===old));
      saveLocal();render();return;
    }
    // Global uniqueness includes pending additions and proposed ID changes.
    const otherPending=draft.filter(x=>x.op==='rename_id'&&x.id!==old).map(x=>x.new_id);
    const otherIds=all().filter(x=>x.id!==old).map(x=>x.id);
    const added=draft.filter(x=>x.op==='add').map(x=>x.after?.id);
    if([...otherPending,...otherIds,...added].includes(newId))return flash('ID 已被其他項目或草稿使用：'+newId);
    const oldOp=pendingFor(old);
    const op={op:'rename_id',type:item.type,id:old,new_id:newId,before:{id:old,type:item.type},notes:['網站內部引用與錨點會同步更新；舊 ID 不保留']};
    if(oldOp)Object.assign(oldOp,op);
    else draft.push(op);
    saveLocal();render();flash('ID 修改已加入草稿；請在右側預覽後送出');
  }
  function setup(){
    const types=byId('itemIdType');if(!types)return;
    const choices=[...new Set(all().map(x=>x.type))].sort();
    types.innerHTML='<option value="">全部</option>'+choices.map(t=>`<option value="${html(t)}">${html(t)}</option>`).join('');
    byId('itemIdSearch')?.addEventListener('input',e=>{query=e.target.value.trim().toLowerCase();render();});
    types.addEventListener('change',e=>{kind=e.target.value;render();});
    byId('itemIdRecords')?.addEventListener('click',e=>{
      const rename=e.target.closest('[data-stage-id]');
      const cancel=e.target.closest('[data-revert-id]');
      if(rename){const old=rename.dataset.stageId;
        const input=[...byId('itemIdRecords').querySelectorAll('[data-proposed-id]')].find(node=>node.dataset.proposedId===old);
        stage(old,String(input?.value||'').trim());
      } else if(cancel){draft=draft.filter(x=>!(x.op==='rename_id'&&x.id===cancel.dataset.revertId));saveLocal();render();}
    });
    render();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',setup,{once:true});else setup();
})();

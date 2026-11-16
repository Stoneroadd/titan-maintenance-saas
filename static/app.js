const tenant = document.querySelector('#tenant'), statusFilter = document.querySelector('#status'), form = document.querySelector('#form');
form.elements.due_date.value = new Date().toLocaleDateString('en-CA');
const labels = {open:'Abierta', in_progress:'En curso', closed:'Cerrada'};
async function api(path, options={}) { const response = await fetch(path,{...options,headers:{'Content-Type':'application/json','X-Tenant-ID':tenant.value,...options.headers}}); const data=await response.json(); if(!response.ok) throw new Error(data.error||'Error de servicio'); return data; }
async function load() {
  const query=statusFilter.value?`?status=${encodeURIComponent(statusFilter.value)}`:'';
  const {orders}=await api('/api/orders'+query); const list=document.querySelector('#orders'); list.replaceChildren();
  if(!orders.length){const p=document.createElement('p');p.className='empty';p.textContent='No hay órdenes para mostrar. Crea una orden para iniciar el tablero.';list.append(p);return;}
  for(const order of orders){const card=document.createElement('section');card.className='order';
    const title=document.createElement('h3');title.textContent=order.title;card.append(title);
    const actions=document.createElement('div');actions.className='actions';
    const select=document.createElement('select');select.setAttribute('aria-label',`Estado de ${order.title}`);
    for(const value of ['open','in_progress','closed']){const option=document.createElement('option');option.value=value;option.textContent=labels[value];option.selected=value===order.status;select.append(option);}
    select.addEventListener('change',async()=>{try{await api(`/api/orders/${order.id}`,{method:'PATCH',body:JSON.stringify({status:select.value})});await load();}catch(e){document.querySelector('#message').textContent=e.message;}});
    const remove=document.createElement('button');remove.className='delete';remove.type='button';remove.textContent='Eliminar';remove.addEventListener('click',async()=>{try{await api(`/api/orders/${order.id}`,{method:'DELETE'});await load();}catch(e){document.querySelector('#message').textContent=e.message;}});
    actions.append(select,remove);card.append(actions);
    const meta=document.createElement('div');meta.className='meta';meta.textContent=`${order.asset_code} · objetivo ${order.due_date}`;
    const pill=document.createElement('span');pill.className='pill';pill.textContent=`Prioridad ${order.priority}`;meta.append(pill);card.append(meta);
    if(order.description){const desc=document.createElement('p');desc.textContent=order.description;card.append(desc);}list.append(card);
  }
}
tenant.addEventListener('change',()=>load().catch(showError));statusFilter.addEventListener('change',()=>load().catch(showError));
form.addEventListener('submit',async e=>{e.preventDefault();const message=document.querySelector('#message');message.textContent='';const values=Object.fromEntries(new FormData(form));try{await api('/api/orders',{method:'POST',body:JSON.stringify(values)});form.elements.asset_code.value='';form.elements.title.value='';form.elements.description.value='';form.elements.priority.value='normal';await load();}catch(error){message.textContent=error.message;}});
function showError(error){document.querySelector('#message').textContent=error.message;}
load().catch(showError);

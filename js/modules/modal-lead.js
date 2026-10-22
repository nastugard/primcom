import { trackYandexGoal, getPageContext } from './analytics.js?v=20261018-organic-1';

const DEFAULT_ENDPOINT = 'https://api.primcom.ru/api/lead';
const GROUP_ID = -1003540261166;
const fieldValue = (form, name) => String(form.elements.namedItem(name)?.value || '').trim();

export function initLeadModal() {
  const modal = document.querySelector('[data-lead-modal]');
  if (!modal || modal.dataset.initialized) return;
  modal.dataset.initialized = 'true';
  const form = modal.querySelector('[data-lead-form]');
  const dialog = modal.querySelector('[role="dialog"]');
  const status = modal.querySelector('[data-form-status]');
  const contextEl = modal.querySelector('[data-lead-context]');
  const title = modal.querySelector('#lead-modal-title');
  const submit = form.querySelector('[type="submit"]');
  let opener = null;
  let context = {};
  let busy = false;
  let started = false;
  let previousOverflow = '';
  const setStatus = (message, type='') => { status.textContent=message; status.dataset.type=type; };
  const track = (name, params={}) => trackYandexGoal(name, {...getPageContext(), ...context, ...params});

  function open(button) {
    if (!modal.hidden) return;
    opener = button || document.activeElement;
    context = {
      model: button?.dataset.leadModel || document.body.dataset.leadModel || '',
      collection: button?.dataset.leadCollection || document.body.dataset.leadCollection || '',
      intent: button?.dataset.leadIntent || 'selection',
    };
    const labels = [context.model, button?.dataset.leadLabel || ''].filter(Boolean);
    contextEl.textContent = labels.join(' · ');
    contextEl.hidden = !labels.length;
    title.textContent = context.model ? `Расчёт ${context.model}` : (button?.dataset.leadTitle || 'Подобрать автомобиль');
    if (button?.dataset.leadBudget) form.elements.namedItem('budget').value = button.dataset.leadBudget;
    setStatus('');
    started=false;
    previousOverflow=document.body.style.overflow;
    modal.hidden=false;
    document.body.style.overflow='hidden';
    form.elements.namedItem('name').focus({preventScroll:true});
    track('lead_form_open');
  }
  function close() {
    if (modal.hidden || busy) return;
    modal.hidden=true;
    document.body.style.overflow=previousOverflow;
    if (opener?.isConnected) opener.focus({preventScroll:true});
  }
  // Охватывает и кнопки в карточках, добавленных после загрузки API.
  document.addEventListener('click', (event) => {
    const button=event.target.closest('[data-open-lead-modal]');
    if (button) { event.preventDefault(); open(button); return; }
    if (event.target.closest('[data-modal-close]')?.closest('[data-lead-modal]') === modal) close();
  });
  document.addEventListener('keydown', (event) => {
    if(modal.hidden)return;
    if(event.key==='Escape'){event.preventDefault();close();return;}
    if(event.key!=='Tab')return;
    const controls=[...dialog.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled])')].filter(el=>el.tabIndex>=0 && el.getClientRects().length);
    const first=controls[0],last=controls.at(-1);
    if(event.shiftKey && (document.activeElement===first || !dialog.contains(document.activeElement))){event.preventDefault();last?.focus();}
    else if(!event.shiftKey && (document.activeElement===last || !dialog.contains(document.activeElement))){event.preventDefault();first?.focus();}
  });
  form.addEventListener('input',()=>{if(!started){started=true;track('lead_form_start');}});
  form.addEventListener('invalid',()=>track('lead_form_error',{reason:'validation'}),true);
  form.addEventListener('submit',async(event)=>{
    event.preventDefault();
    if(busy)return;
    if(fieldValue(form,'company')){setStatus('Не удалось отправить заявку.','error');return;}
    const phone=fieldValue(form,'phone');
    if(phone.replace(/\D/g,'').length<10){setStatus('Укажите телефон с кодом города или страны.','error');form.elements.namedItem('phone').focus();track('lead_form_error',{reason:'phone'});return;}
    if(!form.reportValidity())return;
    const calculator=opener?.closest('[data-import-calculator]');
    const calculation=calculator?.dataset.leadCalculation || '';
    const comment=[contextEl.textContent,fieldValue(form,'city') && `Город получения: ${fieldValue(form,'city')}`,fieldValue(form,'budget') && `Бюджет: ${fieldValue(form,'budget')}`,fieldValue(form,'comment'),calculation].filter(Boolean).join('\n').slice(0,2500);
    const payload={name:fieldValue(form,'name'),phone,comment,chat_id:GROUP_ID,source:'site_modal',page_url:`${location.origin}${location.pathname}`,user_agent:navigator.userAgent};
    busy=true;submit.disabled=true;form.setAttribute('aria-busy','true');setStatus('Отправляем заявку…','pending');
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),12000);
    try{
      const headers={'Content-Type':'application/json'};
      if(typeof window.PRIMCOM_LEAD_TOKEN==='string' && window.PRIMCOM_LEAD_TOKEN.trim())headers['X-Primcom-Token']=window.PRIMCOM_LEAD_TOKEN.trim();
      const endpoint=typeof window.PRIMCOM_LEAD_ENDPOINT==='string' && window.PRIMCOM_LEAD_ENDPOINT.trim() || DEFAULT_ENDPOINT;
      const response=await fetch(endpoint,{method:'POST',headers,body:JSON.stringify(payload),signal:controller.signal});
      if(!response.ok)throw new Error(response.status===429?'rate_limit':'server');
      const result=await response.json();
      if(result?.ok !== true)throw new Error('server');
      track('lead_submit_success',{has_comment:fieldValue(form,'comment')?'1':'0'});
      setStatus('Заявка отправлена. Менеджер свяжется с вами и уточнит расчёт.','success');
      form.reset();
      status.focus();
    }catch(error){
      const reason=error.name==='AbortError'?'timeout':error.message==='rate_limit'?'rate_limit':'server';
      setStatus(reason==='rate_limit'?'Слишком много попыток. Подождите минуту и повторите.':'Не удалось подтвердить отправку. Позвоните +7 953 222-22-75 или повторите позже.','error');
      track('lead_form_error',{reason});
      // После таймаута сервер мог уже принять заявку; повтор автоматически не отправляем.
    }finally{clearTimeout(timer);busy=false;submit.disabled=false;form.removeAttribute('aria-busy');}
  });
}

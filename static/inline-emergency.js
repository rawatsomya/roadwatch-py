(() => {
  let currentId = null, refresh = null;
  const $ = id => document.getElementById(id);
  async function api(url, options) {
    const r = await fetch(url, options);
    const d = await r.json();
    if (!r.ok) throw Error(d.detail || 'Request failed');
    return d;
  }
  const json = value => ({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)});
  function status(msg) { $('rw-status').textContent = msg; }
  function setLink(inputId, linkId) {
    const number = $(inputId).value.trim();
    const valid = /^\+?[0-9\s()\-]{5,20}$/.test(number);
    const a = $(linkId);
    if (valid) { a.href='tel:'+number.replace(/[^+\d]/g,'');a.classList.remove('rw-disabled');a.removeAttribute('aria-disabled'); }
    else { a.removeAttribute('href');a.classList.add('rw-disabled');a.setAttribute('aria-disabled','true'); }
  }
  async function messages() {
    if (!currentId) return;
    try {
      const rows=await api('/api/emergency/'+encodeURIComponent(currentId)+'/messages');
      const box=$('rw-messages');box.replaceChildren();
      for (const row of rows) {
        const p=document.createElement('p');
        p.textContent=(row.sender==='operator'?'Operator':'Hospital demo')+': '+row.text;
        box.appendChild(p);
      }
    } catch(e) { status(e.message); }
  }
  async function verify(confirmed) {
    if (!currentId) return;
    $('rw-verify').disabled=true;$('rw-dismiss').disabled=true;
    try {
      await api('/api/emergency/'+encodeURIComponent(currentId)+'/verify',json({confirmed}));
      $('rw-decision').classList.add('hide');
      $('rw-contacts').classList.toggle('hide',!confirmed);
      status(confirmed?'Accident verified. Use the contacts below to initiate a call.':'Incident dismissed. No contacts notified.');
      clearInterval(refresh);
      if (confirmed) { await messages();refresh=setInterval(messages,3000); }
    } catch(e) { status(e.message);$('rw-verify').disabled=false;$('rw-dismiss').disabled=false; }
  }
  window.roadwatchInlineEmergency=(id,events)=>{
    clearInterval(refresh);currentId=events?.length?id:null;
    $('rw-inline').classList.toggle('hide',!currentId);
    if (!currentId) return;
    $('rw-contacts').classList.add('hide');$('rw-decision').classList.remove('hide');
    $('rw-verify').disabled=false;$('rw-dismiss').disabled=false;
    status(events.length+' possible accident alert(s). Verify the footage before contacting anyone.');
  };
  document.addEventListener('DOMContentLoaded',()=>{
    $('rw-verify').addEventListener('click',()=>verify(true));
    $('rw-dismiss').addEventListener('click',()=>verify(false));
    for (const [input,link,key] of [
      ['rw-ambulance-number','rw-ambulance-call','rw-ambulance-contact'],
      ['rw-doctor-number','rw-doctor-call','rw-doctor-contact']
    ]) {
      $(input).value=localStorage.getItem(key)||'';
      setLink(input,link);
      $(input).addEventListener('input',()=>{localStorage.setItem(key,$(input).value);setLink(input,link);});
    }
    $('rw-message-form').addEventListener('submit',async e=>{
      e.preventDefault();const input=$('rw-message');const text=input.value.trim();if(!text||!currentId)return;
      try {await api('/api/emergency/'+encodeURIComponent(currentId)+'/messages',json({sender:'operator',text}));input.value='';await messages();}
      catch(err){status(err.message);}
    });
  });
})();

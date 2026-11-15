(() => {
  let jobId = null;
  let refresh = null;
  const $ = id => document.getElementById(id);
  async function request(url, options) {
    const r = await fetch(url, options);
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || 'Request failed');
    return data;
  }
  async function loadMessages() {
    if (!jobId) return;
    try {
      const msgs = await request(`/api/emergency/${jobId}/messages`);
      const list = $('rw-messages');
      list.replaceChildren();
      msgs.forEach(m => {
        const el = document.createElement('p');
        el.textContent = `${m.sender}: ${m.text}`;
        list.appendChild(el);
      });
    } catch (e) { $('rw-status').textContent = e.message; }
  }
  window.roadwatchEmergency = function (id, events) {
    jobId = id;
    clearInterval(refresh);
    const panel = $('rw-emergency');
    if (!panel) return;
    panel.hidden = !events?.length;
    if (!events?.length) return;
    $('rw-status').textContent = `${events.length} possible incident(s). Verify before contacting anyone.`;
    $('rw-actions').hidden = false;
    $('rw-chat').hidden = true;
    $('rw-verify').disabled = false;
    $('rw-dismiss').disabled = false;
  };
  async function verify(confirmed) {
    try {
      const result = await request(`/api/emergency/${jobId}/verify`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({confirmed})
      });
      $('rw-status').textContent = confirmed ? 'Verified. Hospital demo chat is now available.' : 'Dismissed. No external alert sent.';
      $('rw-actions').hidden = true;
      $('rw-chat').hidden = !confirmed;
      if (confirmed) { await loadMessages(); refresh = setInterval(loadMessages, 2500); }
    } catch(e) { $('rw-status').textContent = e.message; }
  }
  document.addEventListener('DOMContentLoaded', () => {
    $('rw-verify').onclick = () => verify(true);
    $('rw-dismiss').onclick = () => verify(false);
    $('rw-send').onclick = async () => {
      const input = $('rw-input');
      if (!input.value.trim()) return;
      try {
        await request(`/api/emergency/${jobId}/messages`, {
          method: 'POST', headers: {'Content-Type':'application/json'},
          body: JSON.stringify({sender:'operator', text:input.value})
        });
        input.value = '';
        await loadMessages();
      } catch(e) { $('rw-status').textContent = e.message; }
    };
  });
})();

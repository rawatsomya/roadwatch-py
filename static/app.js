const $ = id => document.getElementById(id);
const drop = $('drop'), file = $('file');
const CIRC = 327;

drop.onclick = () => file.click();
drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); };
drop.ondragleave = () => drop.classList.remove('over');
drop.ondrop = e => { e.preventDefault(); drop.classList.remove('over'); upload(e.dataTransfer.files[0]); };
file.onchange = () => upload(file.files[0]);
$('again').onclick = () => {
  $('result').classList.add('hide');
  $('uploadCard').classList.remove('hide');
  drop.classList.remove('hide');
  $('prog').classList.add('hide');
  file.value = '';
};

function setProgress(p, msg, step) {
  $('arc').style.strokeDashoffset = CIRC - (CIRC * p / 100);
  $('pct').textContent = p + '%';
  if (msg) $('msg').textContent = msg;
  ['s1','s2','s3','s4'].forEach((s, i) => $(s).classList.toggle('on', i < step));
}

async function upload(f) {
  if (!f) return;
  drop.classList.add('hide'); $('prog').classList.remove('hide'); $('result').classList.add('hide');
  $('fname').textContent = f.name;
  setProgress(0, 'Uploading video…', 1);
  const fd = new FormData(); fd.append('file', f);
  const r = await fetch('/api/analyze', { method: 'POST', body: fd });
  if (!r.ok) { $('msg').textContent = 'Error: ' + (await r.json()).detail; return; }
  poll((await r.json()).job_id);
}

async function poll(id) {
  const j = await (await fetch('/api/jobs/' + id)).json();
  if (j.status === 'error') { $('msg').textContent = 'Failed: ' + j.error; return; }
  if (j.status === 'processing') {
    const step = j.progress < 40 ? 2 : j.progress < 85 ? 3 : 4;
    setProgress(j.progress, 'Analyzing footage…', step);
    return setTimeout(() => poll(id), 1000);
  }
  setProgress(100, 'Done!', 4);
  setTimeout(() => show(j), 400);
}

function seek(t) {
  const v = $('vid');
  v.currentTime = Math.max(0, t - 1);
  v.play();
  v.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function show(j) {
  $('uploadCard').classList.add('hide'); $('result').classList.remove('hide');
  const n = j.events.length, top = n ? Math.max(...j.events.map(e => e.confidence)) : 0;
  $('banner').className = 'banner ' + (n ? 'bad' : 'ok');
  $('banner').innerHTML = n
    ? `⚠ ${n} possible accident${n > 1 ? 's' : ''} detected in this footage`
    : '✓ No accidents detected in this footage';
  $('sAcc').textContent = n;
  $('sDur').textContent = j.duration + 's';
  $('sFr').textContent = j.frames.toLocaleString();
  $('sConf').textContent = n ? Math.round(top * 100) + '%' : '–';
  $('vid').src = j.video;
  $('dl').href = j.video;
  $('tl').innerHTML = j.events.map(e =>
    `<div class="mark" style="left:${(e.time / j.duration) * 100}%" title="${e.time}s" onclick="seek(${e.time})"></div>`
  ).join('');
  $('events').innerHTML = n
    ? j.events.map(e => `<div class="ev" onclick="seek(${e.time})">
        <img src="${e.snapshot}" alt="snapshot">
        <div class="info"><div><span class="tag">ACCIDENT</span>
        <div class="mut" style="margin-top:6px">at ${e.time}s · frame ${e.frame}</div>
        <div class="meter"><i style="width:${e.confidence * 100}%"></i></div></div>
        <b>${Math.round(e.confidence * 100)}%</b></div></div>`).join('')
    : '<p class="mut">Nothing suspicious found. Roads look safe 🎉</p>';
}
/* PDS v2 — frontend logic */

const dropZone     = document.getElementById('drop-zone');
const fileInput    = document.getElementById('file-input');
const fileListWrap = document.getElementById('file-list-wrap');
const fileTbody    = document.getElementById('file-tbody');
const fileCountLbl = document.getElementById('file-count-label');
const clearBtn     = document.getElementById('clear-btn');
const runBtn       = document.getElementById('run-btn');
const spinner      = document.getElementById('spinner');
const spinnerLabel = document.getElementById('spinner-label');
const threshRange  = document.getElementById('threshold-range');
const threshNum    = document.getElementById('threshold');
const sectionRes   = document.getElementById('section-results');
const statsRow     = document.getElementById('stats-row');
const flaggedTbody = document.getElementById('flagged-tbody');
const allTbody     = document.getElementById('all-tbody');
const noFlagged    = document.getElementById('no-flagged');

// ── Threshold sync ──────────────────────────────────────────────────────────
threshRange.addEventListener('input', () => threshNum.value = threshRange.value);
threshNum.addEventListener('input', () => {
  const v = Math.min(100, Math.max(0, parseInt(threshNum.value) || 0));
  threshRange.value = v;
  threshNum.value   = v;
});

// ── Drag & Drop ─────────────────────────────────────────────────────────────
dropZone.addEventListener('click', (e) => {
  if (e.target.tagName !== 'LABEL') fileInput.click();
});

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('dragging');
});

dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragging'));

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragging');
  uploadFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', () => uploadFiles(fileInput.files));

// ── Upload ───────────────────────────────────────────────────────────────────
async function uploadFiles(fileList) {
  if (!fileList || fileList.length === 0) return;

  const formData = new FormData();
  for (const f of fileList) formData.append('files', f);

  setSpinner(true, 'Uploading…');
  runBtn.disabled = true;

  try {
    const res  = await fetch('/upload', { method: 'POST', body: formData });
    const data = await res.json();

    if (data.error) { alert(data.error); return; }

    renderFileList(data.files);
  } catch (err) {
    alert('Upload failed: ' + err.message);
  } finally {
    setSpinner(false);
  }
}

function renderFileList(files) {
  fileTbody.innerHTML = '';
  let okCount = 0;

  for (const f of files) {
    const tr = document.createElement('tr');
    const pillClass = f.status === 'ok' ? 'pill-ok'
                    : f.status === 'duplicate' ? 'pill-duplicate'
                    : 'pill-warning';
    tr.innerHTML = `
      <td style="font-family:monospace;font-size:12px">${esc(f.filename)}</td>
      <td><strong>${esc(f.roll)}</strong></td>
      <td><span class="pill ${pillClass}">${f.status}</span></td>
      <td style="color:var(--text-3)">${esc(f.note)}</td>
    `;
    fileTbody.appendChild(tr);
    if (f.status === 'ok' || f.status === 'warning') okCount++;
  }

  fileCountLbl.textContent = `${okCount} valid file(s) · ${files.length} total`;
  fileListWrap.classList.remove('hidden');
  runBtn.disabled = okCount < 2;
}

// ── Clear ────────────────────────────────────────────────────────────────────
clearBtn.addEventListener('click', async () => {
  await fetch('/clear', { method: 'POST' });
  fileTbody.innerHTML = '';
  fileListWrap.classList.add('hidden');
  sectionRes.classList.add('hidden');
  runBtn.disabled = true;
  fileInput.value = '';
});

// ── Run Analysis (background job + progress polling) ─────────────────────────
const cancelBtn = document.getElementById('cancel-btn');
let currentJob = null;

function fmtTime(sec) {
  sec = Math.max(0, Math.round(sec));
  const m = Math.floor(sec / 60), s = sec % 60;
  return m ? `${m}m ${s}s` : `${s}s`;
}

function finishRun() {
  currentJob = null;
  setSpinner(false);
  cancelBtn.classList.add('hidden');
  runBtn.disabled = false;
}

cancelBtn.addEventListener('click', async () => {
  if (!currentJob) return;
  spinnerLabel.textContent = 'Cancelling…';
  cancelBtn.disabled = true;
  try { await fetch('/cancel/' + currentJob, { method: 'POST' }); } catch (_) {}
});

runBtn.addEventListener('click', async () => {
  const threshold = parseInt(threshNum.value) || 70;
  const language  = document.getElementById('language').value;

  setSpinner(true, 'Starting analysis…');
  runBtn.disabled = true;
  cancelBtn.disabled = false;
  cancelBtn.classList.remove('hidden');

  try {
    const res  = await fetch('/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ threshold, language }),
    });
    const data = await res.json();
    if (data.error) { alert(data.error); finishRun(); return; }

    currentJob = data.job_id;
    pollProgress(data.job_id, threshold);
  } catch (err) {
    alert('Analysis failed: ' + err.message);
    finishRun();
  }
});

async function pollProgress(jobId, threshold) {
  if (currentJob !== jobId) return;
  try {
    const res = await fetch('/progress/' + jobId);
    const p   = await res.json();

    if (p.status === 'done') {
      finishRun();
      renderResults(p.result, threshold);
      return;
    }
    if (p.status === 'error') {
      finishRun();
      alert(p.error || 'Analysis failed.');
      return;
    }
    if (p.status === 'cancelled') {
      finishRun();
      return;
    }

    // running — show stage, counts, elapsed and a rough ETA
    let label = `${p.stage}…`;
    if (p.total > 1 || p.stage === 'Comparing pairs') {
      const pct = p.total ? Math.round((p.done / p.total) * 100) : 0;
      label = `${p.stage}: ${p.done}/${p.total} (${pct}%)`;
      if (p.stage === 'Comparing pairs' && p.done > 0) {
        const eta = (p.elapsed / p.done) * (p.total - p.done);
        label += ` · ~${fmtTime(eta)} left`;
      }
    }
    label += ` · ${fmtTime(p.elapsed)} elapsed`;
    spinnerLabel.textContent = label;
  } catch (err) {
    spinnerLabel.textContent = 'Waiting for server…';
  }
  setTimeout(() => pollProgress(jobId, threshold), 1000);
}

// ── Render Results ────────────────────────────────────────────────────────────
function renderResults(data, threshold) {
  // Stats
  statsRow.innerHTML = `
    ${stat('Students', data.total_students)}
    ${stat('Pairs Compared', data.total_pairs)}
    ${stat('Flagged', data.flagged_count)}
    ${stat('Language', data.language.toUpperCase())}
    ${data.unreadable.length ? stat('Unreadable', data.unreadable.length) : ''}
  `;

  // Flagged table
  flaggedTbody.innerHTML = '';
  if (data.flagged_pairs.length === 0) {
    noFlagged.classList.remove('hidden');
    document.getElementById('flagged-table').classList.add('hidden');
  } else {
    noFlagged.classList.add('hidden');
    document.getElementById('flagged-table').classList.remove('hidden');
    for (const r of data.flagged_pairs)
      flaggedTbody.appendChild(makeRow(r, threshold));
  }

  // All pairs table
  allTbody.innerHTML = '';
  for (const r of data.all_pairs)
    allTbody.appendChild(makeRow(r, threshold));

  sectionRes.classList.remove('hidden');
  sectionRes.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function stat(label, value) {
  return `
    <div class="stat-card">
      <div class="stat-label">${label}</div>
      <div class="stat-value">${value}</div>
    </div>
  `;
}

function makeRow(r, threshold) {
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><strong>${esc(r.roll_a)}</strong></td>
    <td><strong>${esc(r.roll_b)}</strong></td>
    <td>${scoreCell(r.similarity)}</td>
    <td style="color:var(--text-2)">${r.seq_score}%</td>
    <td style="color:var(--text-2)">${r.fuzzy_score}%</td>
  `;
  return tr;
}

function scoreCell(score) {
  const cls = score >= 90 ? 'score-red'
            : score >= 70 ? 'score-orange'
            : score >= 50 ? 'score-yellow'
            : 'score-grey';
  return `<span class="score-cell ${cls}">${score}%</span>`;
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
    tab.classList.add('active');
    document.getElementById('tab-' + tab.dataset.tab).classList.remove('hidden');
  });
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function setSpinner(show, label = '') {
  spinner.classList.toggle('hidden', !show);
  spinnerLabel.textContent = label;
}

function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

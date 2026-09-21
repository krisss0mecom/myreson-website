const form = document.querySelector('#contribute-form');
const outcome = document.querySelector('#outcome');
const mode = document.querySelector('#entry-mode');
const question = document.querySelector('#question');
const button = document.querySelector('#send');
const payloadInput = document.querySelector('#payload');
let challenges = [];

mode.addEventListener('change', () => {
  document.querySelector('#guided-entry').hidden = mode.value !== 'guided';
  document.querySelector('#json-entry').hidden = mode.value !== 'json';
});

for (const name of ['claim', 'evidence', 'falsification']) {
  const input = document.getElementById(name);
  input.addEventListener('input', () => {
    const count = [...input.value].length;
    document.getElementById(name + '-count').textContent = count.toLocaleString('en') + ' / 20,000';
  });
}

function context() {
  document.querySelector('#question-context').href = '/research/' + Number(question.value) + '.html';
  document.querySelector('#base-revision').value = '';
}

fetch(form.dataset.inbox + '/challenges.json', { credentials: 'omit', signal: AbortSignal.timeout(15000) }).then(async (response) => {
  if (!response.ok) throw new Error('Open questions unavailable; keep your draft and retry later.');
  challenges = await response.json();
  question.replaceChildren(...challenges.map((item) => new Option(item.id + '. ' + item.title, item.id)));
  const selected = new URL(location.href).searchParams.get('question');
  if (challenges.some((item) => String(item.id) === selected)) question.value = selected;
  context();
}).catch((error) => { outcome.textContent = error.message; });
question.addEventListener('change', context);

function draft() {
  let payload;
  if (mode.value === 'json') {
    payload = JSON.parse(payloadInput.value);
  } else {
    const entry = challenges.find((item) => item.id === Number(question.value));
    if (!entry) throw new Error('Choose an available question.');
    payload = { question_id: entry.id, source_sha256: entry.source_sha256 };
    for (const name of ['type', 'claim', 'evidence', 'falsification', 'work_status']) payload[name] = document.getElementById(name).value;
    const revision = document.querySelector('#base-revision').value.trim();
    if (revision) payload.base_revision_sha256 = revision;
  }
  if (!payload || Array.isArray(payload) || typeof payload !== 'object') throw new Error('The contribution must be one JSON object.');
  for (const name of ['claim', 'evidence', 'falsification']) {
    if (typeof payload[name] !== 'string' || !payload[name].trim() || [...payload[name]].length > 20000) throw new Error(name + ' must contain 1–20,000 Unicode characters. Nothing has been truncated.');
  }
  const serialized = JSON.stringify(payload);
  if (new TextEncoder().encode(serialized).length > 262144) throw new Error('The complete submission exceeds 256 KiB.');
  return serialized;
}

document.querySelector('#download-draft').addEventListener('click', () => {
  try {
    const blob = new Blob([draft()], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'reson-contribution.json';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    outcome.textContent = 'Draft download requested. This does not submit or publish anything.';
  } catch (error) { outcome.textContent = error.message; }
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (button.disabled) return;
  if (!document.querySelector('#consent').checked) { outcome.textContent = 'Confirm that you are authorized to share this material for provisional publication.'; return; }
  let serialized;
  try { serialized = draft(); } catch (error) { outcome.textContent = 'Check your draft: ' + error.message; return; }
  button.disabled = true;
  outcome.textContent = 'Sending to the review inbox…';
  try {
    const response = await fetch(form.dataset.inbox + '/v1/submissions', { method: 'POST', credentials: 'omit', headers: { 'Content-Type': 'application/json' }, body: serialized, signal: AbortSignal.timeout(15000) });
    const raw = await response.text();
    let data;
    try { data = JSON.parse(raw); } catch { throw new Error('The host returned a non-JSON response (HTTP ' + response.status + ').'); }
    if (response.status !== 202 || !/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(data.receipt)) throw new Error(data.error || 'Not received (HTTP ' + response.status + ').');
    outcome.replaceChildren();
    const message = document.createElement('p');
    message.textContent = (data.duplicate ? 'Already received; this is the existing contribution, not a new review. ' : 'Received for review, not yet publication. ') + 'Receipt: ' + data.receipt;
    const track = document.createElement('a');
    track.href = '/track.html#' + data.receipt;
    track.textContent = 'Track this contribution →';
    outcome.append(message, track);
  } catch (error) { outcome.textContent = error.message + ' Your draft is still here. If the outcome is uncertain, retry the identical payload; it is deduplicated.'; }
  finally { button.disabled = false; }
});

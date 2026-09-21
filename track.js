const form = document.querySelector('#track-form');
const receipt = document.querySelector('#receipt');
const result = document.querySelector('#tracking-result');
const button = form.querySelector('button');
const states = { queued: 'Queued for review', accepted: 'Accepted · awaiting confirmed publication', published: 'Published · provisional findings', quarantined: 'Quarantined · not published', rejected: 'Not accepted', withdrawn: 'Withdrawn' };
const reasons = { code: 'Code or code-like formatting requires separate inspection.', url: 'A referenced domain is outside the allowed sources.', personal_data: 'Possible personal information.', credential: 'Possible credential.', reviewer_instruction: 'Text appears to direct the reviewer.', uncertain: 'The review could not safely establish acceptance.', unsafe_model_output: 'The proposed review did not pass the publication gate.', irrelevant: 'Outside the question’s scope.', duplicate: 'No new contribution identified.', invalid_source: 'The question version could not be matched.', rolled_back: 'Withdrawn by a rollback.' };
const initial = location.hash.slice(1);
if (/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(initial)) receipt.value = initial;

function paragraph(text) {
  const element = document.createElement('p');
  element.textContent = text;
  result.append(element);
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!form.reportValidity() || button.disabled) return;
  button.disabled = true;
  result.textContent = 'Checking the hosted status…';
  try {
    const response = await fetch(form.dataset.inbox + '/v1/status/' + receipt.value.trim(), { credentials: 'omit', cache: 'no-store', signal: AbortSignal.timeout(15000) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Status unavailable.');
    if (!Object.hasOwn(states, data.state)) throw new Error('Unrecognized status; keep your receipt and retry later.');
    result.replaceChildren();
    const heading = document.createElement('h2');
    heading.textContent = states[data.state];
    result.append(heading);
    paragraph('Question ' + data.question_id + ' · Receipt ' + data.receipt);
    for (const reason of data.reason_codes || []) paragraph(reasons[reason] || 'Held by a safety or review check: ' + reason);
    paragraph(data.last_synced_at ? 'Last synchronized: ' + new Date(data.last_synced_at * 1000).toISOString() : 'No worker synchronization yet.');
    if (data.status_stale) paragraph('This status is stale or has not yet synchronized. It is not a claim that the worker is currently running.');
    if (Number.isSafeInteger(data.question_id) && data.question_id > 0) {
      const link = document.createElement('a');
      link.href = '/research/' + data.question_id + '.html';
      link.textContent = 'Open the research workspace →';
      result.append(link);
      if (data.state === 'published' && /^[a-f0-9]{64}$/.test(data.revision_sha256)) {
        const revision = document.createElement('a');
        revision.href = '/progress/history/' + data.question_id + '/' + data.revision_sha256 + '.json';
        revision.textContent = 'Inspect the published revision';
        const row = document.createElement('p');
        row.append(revision);
        result.append(row);
      }
    }
  } catch (error) { result.textContent = error.message + ' Your receipt has not been changed. A network error does not mean rejection.'; }
  finally { button.disabled = false; }
});
if (receipt.value) form.requestSubmit();

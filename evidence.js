const choice = document.querySelector('#finding-choice');
const detail = document.querySelector('#evidence-detail');
const relations = document.querySelector('#evidence-relations');
const wantedQuestion = new URL(location.href).searchParams.get('question');

function element(tag, text) {
  const node = document.createElement(tag);
  node.textContent = text;
  return node;
}

async function start() {
  const response = await fetch('/progress/graph.json', { credentials: 'omit' });
  if (!response.ok) throw new Error('The evidence graph is currently unavailable.');
  const graph = await response.json();
  const findings = graph.nodes.filter((node) => node.type === 'finding');
  const byId = new Map(findings.map((finding) => [finding.id, finding]));
  const questions = new Map(graph.edges.filter((edge) => edge.kind === 'addresses').map((edge) => [edge.source, edge.target.replace('problem_', '')]));
  choice.replaceChildren(...findings.map((finding) => new Option('Q' + questions.get(finding.id) + ' · ' + finding.id.split('_').slice(1).join(' ').replaceAll('-', ' '), finding.id)));
  const first = findings.find((finding) => questions.get(finding.id) === wantedQuestion);
  if (first) choice.value = first.id;
  function render() {
    const finding = byId.get(choice.value);
    detail.replaceChildren();
    relations.replaceChildren();
    if (!finding) { detail.textContent = 'No reviewed findings yet.'; return; }
    detail.append(element('p', finding.status + ' · provisional'), element('h2', finding.text), element('p', finding.verification));
    const link = element('a', 'View this finding in its research workspace →');
    link.href = '/research/' + questions.get(finding.id) + '.html#' + encodeURIComponent(finding.id);
    detail.append(link);
    const connected = graph.edges.filter((edge) => edge.kind !== 'addresses' && (edge.source === finding.id || edge.target === finding.id));
    for (const edge of connected) {
      const other = byId.get(edge.source === finding.id ? edge.target : edge.source);
      if (!other) continue;
      const card = element('article', '');
      card.className = 'relation-card';
      card.append(element('p', edge.source === finding.id ? 'Selected finding → ' + edge.kind + ' → connected finding' : 'Connected finding → ' + edge.kind + ' → selected finding'), element('h3', other.text), element('p', edge.reason || ''));
      const button = element('button', 'Inspect connected finding');
      button.type = 'button';
      button.addEventListener('click', () => { choice.value = other.id; render(); choice.focus(); });
      card.append(button);
      relations.append(card);
    }
    if (!connected.length) relations.textContent = 'No reviewed claim-to-claim relationship is recorded yet.';
  }
  choice.addEventListener('change', render);
  render();
}
start().catch((error) => { detail.textContent = error.message; choice.replaceChildren(new Option('Unavailable')); });

async function refreshInventory() {
  const response = await fetch('/research/overview.json', { credentials: 'omit', cache: 'no-cache' });
  if (!response.ok) throw new Error('Inventory unavailable');
  const data = await response.json();
  if (data.schema !== 'reson-research-overview/1' || !Array.isArray(data.questions) || data.questions.length > 50) throw new Error('Unexpected inventory');
  const grid = document.querySelector('.mission-grid');
  const cards = [];
  let count = 0;
  for (const item of data.questions) {
    if (!Number.isSafeInteger(item.id) || item.id < 1 || !Number.isSafeInteger(item.findings) || item.findings < 0 || !Number.isSafeInteger(item.round)) throw new Error('Invalid inventory');
    const article = document.createElement('article');
    article.className = 'mission';
    const meta = document.createElement('p');
    meta.className = 'meta';
    meta.textContent = 'Question ' + String(item.id).padStart(2, '0') + ' · ' + (item.round ? 'Round ' + item.round : 'First contribution welcome');
    const title = document.createElement('h3');
    const link = document.createElement('a');
    link.href = '/research/' + item.id + '.html';
    link.textContent = item.title;
    title.append(link);
    const next = document.createElement('p');
    next.textContent = String(item.next_question).slice(0, 260);
    const foot = document.createElement('div');
    foot.className = 'mission-foot';
    const total = document.createElement('span');
    total.textContent = item.findings + ' reviewed findings · provisional';
    const enter = document.createElement('a');
    enter.href = link.href;
    enter.textContent = 'Enter workspace →';
    foot.append(total, enter);
    article.append(meta, title, next, foot);
    cards.push(article);
    count += item.findings;
  }
  grid.replaceChildren(...cards);
  const numbers = document.querySelectorAll('.research-numbers strong');
  numbers[0].textContent = data.questions.length;
  numbers[1].textContent = count;
  document.querySelector('#inventory-status').textContent = 'Inventory refreshed from the published research record. Counts describe findings, not proven discoveries.';
}
refreshInventory().catch(() => { document.querySelector('#inventory-status').textContent = 'Live inventory could not be loaded. The page shows its initial snapshot; open a workspace to check the current revision.'; });

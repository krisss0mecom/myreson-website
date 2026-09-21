const button = document.getElementById('copy-packet');
const packet = document.getElementById('research-packet');
const status = document.getElementById('copy-status');

button.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(packet.value);
    status.textContent = 'Copied. Paste into your AI chat; bring its filled JSON back to the browser form.';
  } catch {
    packet.focus();
    packet.select();
    status.textContent = 'Select and copy the full packet manually. Nothing has been submitted.';
  }
});

document.getElementById('run-btn').addEventListener('click', () => {
  const sequence = document.getElementById('sequence-input').value.trim();
  const viewer = document.getElementById('viewer');
  const btn = document.getElementById('run-btn');
  
  if (!sequence) {
    alert('Please enter a peptide sequence (e.g. ACDEF)');
    return;
  }

  // Basic mock of the loading process
  btn.disabled = true;
  btn.innerText = 'Propagating Dynamics...';
  viewer.innerHTML = `<div style="color: var(--accent-primary); animation: pulse 1s infinite;">Running NO STATE Rollout (kappa_mult=4.0) for ${sequence}...</div>`;
  
  // Simulate backend inference time (fraction of a second, because it's so fast)
  setTimeout(() => {
    btn.innerText = 'Generate Torsion Ensemble';
    btn.disabled = false;
    viewer.innerHTML = `
      <div style="text-align: center; color: var(--accent-primary);">
        <div style="font-size: 3rem; margin-bottom: 1rem;">✨</div>
        <h3 style="color: white; margin-bottom: 0.5rem;">Ensemble Generated</h3>
        <p style="color: var(--text-muted); font-size: 0.9rem;">(3D Visualization Module loading...)</p>
        <p style="color: var(--text-muted); font-size: 0.9rem; margin-top: 1rem;">Sequence: ${sequence}</p>
        <p style="color: var(--text-muted); font-size: 0.9rem;">Model: AlphaDynamics v0.4.2</p>
      </div>
    `;
  }, 1500);
});

// Add keyframe for pulse animation
const style = document.createElement('style');
style.innerHTML = `
  @keyframes pulse {
    0% { opacity: 0.5; }
    50% { opacity: 1; text-shadow: var(--glow); }
    100% { opacity: 0.5; }
  }
`;
document.head.appendChild(style);

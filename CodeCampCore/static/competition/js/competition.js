// Tiny hero text animation + countdown
document.addEventListener('DOMContentLoaded', () => {
  const title = document.querySelector('.cdc-hero-title');
  if (title) {
    const text = title.textContent;
    title.textContent = '';
    let i = 0;
    const interval = setInterval(() => {
      if (i >= text.length) {
        clearInterval(interval);
        return;
      }
      title.textContent += text[i++];
    }, 40);
  }

  const hero = document.querySelector('.cdc-hero[data-start]');
  const timerEl = document.getElementById('cdc-countdown-timer');
  if (!hero || !timerEl) return;

  const startIso = hero.getAttribute('data-start');
  if (!startIso) return;

  const target = new Date(startIso);

  const updateCountdown = () => {
    const now = new Date();
    const diff = target - now;
    if (diff <= 0) {
      timerEl.textContent = 'In progress or finished';
      return;
    }
    const totalSecs = Math.floor(diff / 1000);
    const days = Math.floor(totalSecs / 86400);
    const hours = Math.floor((totalSecs % 86400) / 3600);
    const mins = Math.floor((totalSecs % 3600) / 60);
    const secs = totalSecs % 60;
    timerEl.textContent = `${days}d ${hours}h ${mins}m ${secs}s`;
  };

  updateCountdown();
  setInterval(updateCountdown, 1000);
});

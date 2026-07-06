// ── Auto-dismiss flash messages ──
document.addEventListener('DOMContentLoaded', () => {
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach(f => {
    setTimeout(() => {
      f.style.transition = 'opacity 0.4s';
      f.style.opacity = '0';
      setTimeout(() => f.remove(), 400);
    }, 3500);
  });

  // Set min datetime for expiry fields
  const expiryInput = document.querySelector('input[name="expiry"]');
  if (expiryInput) {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    expiryInput.min = now.toISOString().slice(0, 16);
  }
});

// ── Animated Loading Screen ──
window.addEventListener('load', () => {
  const loader = document.getElementById('loader');
  if (loader) {
    setTimeout(() => {
      loader.style.opacity = '0';
      setTimeout(() => loader.remove(), 400);
    }, 800);
  }
});

// ── Confetti on donation ──
function launchConfetti() {
  const colors = ['#2D6A4F', '#52B788', '#F4A261', '#FFD700', '#FF6B6B'];
  for (let i = 0; i < 100; i++) {
    const confetti = document.createElement('div');
    confetti.className = 'confetti-piece';
    confetti.style.cssText = `
      position: fixed;
      width: ${Math.random() * 10 + 5}px;
      height: ${Math.random() * 10 + 5}px;
      background: ${colors[Math.floor(Math.random() * colors.length)]};
      left: ${Math.random() * 100}vw;
      top: -20px;
      border-radius: ${Math.random() > 0.5 ? '50%' : '0'};
      animation: confettiFall ${Math.random() * 2 + 1.5}s linear forwards;
      animation-delay: ${Math.random() * 0.5}s;
      z-index: 9999;
    `;
    document.body.appendChild(confetti);
    setTimeout(() => confetti.remove(), 3000);
  }
}

// Trigger confetti if success flash exists
document.addEventListener('DOMContentLoaded', () => {
  const successFlash = document.querySelector('.flash-success');
  if (successFlash && successFlash.textContent.includes('listed successfully')) {
    launchConfetti();
  }
});

// ── Image Gallery Lightbox ──
function openLightbox(src, alt) {
  const overlay = document.createElement('div');
  overlay.className = 'lightbox-overlay';
  overlay.innerHTML = `
    <div class="lightbox-content">
      <button class="lightbox-close" onclick="this.closest('.lightbox-overlay').remove()">✕</button>
      <img src="${src}" alt="${alt}" class="lightbox-img"/>
      <p class="lightbox-caption">${alt}</p>
    </div>
  `;
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) overlay.remove();
  });
  document.body.appendChild(overlay);
}

// Make food images clickable
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.food-card-img, .detail-img').forEach(img => {
    img.style.cursor = 'pointer';
    img.addEventListener('click', () => openLightbox(img.src, img.alt));
  });
});
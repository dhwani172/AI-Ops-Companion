// Entrance animations + typewriter + Liquid Ether bootstrap

function typeWriter(text, elementId, speed = 24) {
   const el = document.getElementById(elementId);
   if (!el) return;
   el.innerHTML = '';
   el.style.opacity = 0.9;
   let i = 0;
   (function tick() {
      if (i < text.length) {
         el.innerHTML += text.charAt(i++);
         setTimeout(tick, speed);
      } else if (window.anime) {
         window.anime({ targets: el, opacity: [0.9, 1], duration: 500, easing: 'easeOutQuad' });
      }
   })();
}

(function () {
   const ready = (cb) => (document.readyState !== 'loading' ? cb() : document.addEventListener('DOMContentLoaded', cb));

   // Page entrance
   function animateEntrance() {
      if (!window.anime) return;
      window.anime.set(['.app-title', '.app-subtitle', '.card'], { opacity: 0, translateY: 18 });
      window.anime.timeline({ easing: 'easeOutQuint', duration: 600 })
         .add({ targets: '.app-title', opacity: [0, 1], translateY: [18, 0] })
         .add({ targets: '.app-subtitle', opacity: [0, 1], translateY: [14, 0] }, '-=350')
         .add({ targets: '.card', opacity: [0, 1], translateY: [18, 0] }, '-=250');
   }

   // Liquid Ether background (fixed, fullscreen)
   function initLiquidEther() {
      const root = document.getElementById('liquid-ether-bg');
      if (!root || !window.THREE) return;

      // Make sure it doesn't consume layout space
      root.style.position = 'fixed';
      root.style.inset = '0';
      root.style.pointerEvents = 'none';
      root.style.zIndex = '-1';

      // Minimal fluid render (using your GLSL/WebGL classes ported)
      // For brevity, use a gentle animated gradient if WebGL fails.
      try {
         // If you keep your long WebGL manager from before, call it here.
         // createLiquidEther(root, options)  <-- if you split it out.
         // For now, just create a very light animated canvas background color.
         const canvas = document.createElement('canvas');
         const ctx = canvas.getContext('2d');
         root.appendChild(canvas);

         function resize() {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
         }
         resize();
         window.addEventListener('resize', resize);

         let t = 0;
         (function loop() {
            const w = canvas.width, h = canvas.height;
            const g = ctx.createLinearGradient(0, 0, w, h);
            g.addColorStop(0, '#0a1326');
            g.addColorStop(1, '#101d3a');
            ctx.fillStyle = g;
            ctx.fillRect(0, 0, w, h);

            // soft moving orbs
            const r = 140 + 60 * Math.sin(t * 0.003);
            ctx.globalAlpha = 0.12;
            ctx.beginPath();
            ctx.arc((w / 2) + 220 * Math.cos(t * 0.0008), (h / 2) + 160 * Math.sin(t * 0.0011), r, 0, Math.PI * 2);
            ctx.fillStyle = '#55b2ff';
            ctx.fill();

            ctx.beginPath();
            ctx.arc((w / 2) + 260 * Math.cos(t * 0.0013 + 1.3), (h / 2) + 200 * Math.sin(t * 0.0009 + 0.7), r * 0.9, 0, Math.PI * 2);
            ctx.fillStyle = '#c68fff';
            ctx.fill();

            ctx.globalAlpha = 1;
            t += 16;
            requestAnimationFrame(loop);
         })();
      } catch (e) {
         // fallback: static gradient handled by CSS background
      }
   }

   ready(() => {
      animateEntrance();
      initLiquidEther();
   });

   // Streamlit reruns fire this event; keep background alive
   document.addEventListener('streamlit:rendered', () => {
      initLiquidEther();
   });
})();

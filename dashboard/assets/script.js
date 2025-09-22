(function () {
   const ready = (cb) => (document.readyState !== 'loading'
      ? cb()
      : document.addEventListener('DOMContentLoaded', cb));

   function initRotator() {
      const el = document.getElementById('recipe-rotator');
      if (!el) return;

      const entries = Array.isArray(window.__aiOpsRecipes) && window.__aiOpsRecipes.length
         ? window.__aiOpsRecipes
         : ['Summaries', 'Action Items', 'Brainstorming'];

      let index = 0;
      el.textContent = entries[0];

      if (window.__recipeRotatorInterval) {
         clearInterval(window.__recipeRotatorInterval);
      }

      const swap = () => {
         index = (index + 1) % entries.length;
         const next = entries[index];
         if (window.anime) {
            window.anime.timeline({ duration: 900 })
               .add({ targets: el, opacity: [1, 0], translateY: [0, -8], easing: 'easeInQuad' })
               .add({
                  targets: el,
                  opacity: [0, 1],
                  translateY: [8, 0],
                  easing: 'easeOutQuad',
                  begin: () => { el.textContent = next; }
               });
         } else {
            el.style.transition = 'opacity 0.35s ease, transform 0.35s ease';
            el.style.opacity = 0;
            el.style.transform = 'translateY(-6px)';
            setTimeout(() => {
               el.textContent = next;
               el.style.opacity = 1;
               el.style.transform = 'translateY(0)';
            }, 200);
         }
      };

      window.__recipeRotatorInterval = setInterval(swap, 3600);
   }

   const bootstrap = () => {
      initRotator();
   };

   ready(bootstrap);
   document.addEventListener('streamlit:rendered', bootstrap);
})();

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

function flashBanner(id, ms = 1400) {
   const el = document.getElementById(id);
   if (!el) return;
   if (window.anime) {
      window.anime({ targets: el, opacity: [0, 1, 0], duration: ms, easing: 'easeInOutQuad' });
   } else {
      el.style.transition = 'opacity 0.6s ease';
      el.style.opacity = 1;
      setTimeout(() => (el.style.opacity = 0), ms);
   }
}

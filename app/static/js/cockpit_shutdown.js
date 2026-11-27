/**
 * AirTrack Cockpit Shutdown System
 * Hidden easter egg: two mirrored banks of overhead switches (L1→L4, R1→R4)
 * secure the cockpit into a nighttime hangar state. Reverse to wake.
 * No instructions. No cursor changes. Discovery only.
 */

(function () {
  'use strict';

  const STORAGE = {
    SECURED:  'cockpit_secured',
    BANK:     'active_switch_bank',
    PROGRESS: 'switch_progress',
  };

  const STAGE_CLASSES = ['cockpit--stage-1','cockpit--stage-2','cockpit--stage-3','cockpit--stage-4'];
  const STAGE_DELAY   = 2000; // ms per stage (~8s total)
  const BASE_W = 1536;
  const BASE_H = 1024;

  // Switch coordinates in base image space (1536×1024)
  const SWITCHES = [
    { id:'sw-L1', bank:'L', step:1, px:414, py:401 },
    { id:'sw-L2', bank:'L', step:2, px:438, py:424 },
    { id:'sw-L3', bank:'L', step:3, px:469, py:425 },
    { id:'sw-L4', bank:'L', step:4, px:490, py:405 },
    { id:'sw-R1', bank:'R', step:1, px:1017, py:404 },
    { id:'sw-R2', bank:'R', step:2, px:1040, py:425 },
    { id:'sw-R3', bank:'R', step:3, px:1071, py:425 },
    { id:'sw-R4', bank:'R', step:4, px:1095, py:406 },
  ];

  // State
  let secured  = false;
  let bank     = null;
  let progress = 0;
  let stageTimer = null;

  // DOM refs
  let indicator = null;

  function vintageSwitches() { return document.body.classList.contains('theme-vintage_brass'); }
  function updateSwitchVisuals() {
    // switch patch 1 (Bob 6710): pressed state and labels for every theme, not only Vintage Brass
    SWITCHES.forEach(sw => {
      const zone = document.getElementById('zone-' + sw.id);
      if (!zone) return;
      const off = sw.bank === bank && sw.step <= progress;
      zone.classList.toggle('is-off', off);
      zone.setAttribute('aria-pressed', String(off));
      zone.setAttribute('aria-label', 'Cockpit ' + sw.bank + sw.step + (off ? ' off' : ' on'));
    });
  }

  // ── Storage ──────────────────────────────────────────────────────────────

  function saveState() {
    updateSwitchVisuals();
    try {
      localStorage.setItem(STORAGE.SECURED, String(secured));
      if (bank !== null) {
        localStorage.setItem(STORAGE.BANK, bank);
      } else {
        localStorage.removeItem(STORAGE.BANK);
      }
      localStorage.setItem(STORAGE.PROGRESS, String(progress));
    } catch (_) {}
  }

  function loadState() {
    try {
      secured  = localStorage.getItem(STORAGE.SECURED) === 'true';
      bank     = localStorage.getItem(STORAGE.BANK) || null;
      progress = parseInt(localStorage.getItem(STORAGE.PROGRESS) || '0', 10) || 0;
    } catch (_) { secured = false; bank = null; progress = 0; }
  }

  // ── Visual state ─────────────────────────────────────────────────────────

  function applyStage(stage, instant) {
    const b = document.body;
    STAGE_CLASSES.forEach(c => b.classList.remove(c));
    if (stage > 0) b.classList.add('cockpit--stage-' + stage);
    if (instant) {
      b.classList.add('cockpit--no-transition');
      requestAnimationFrame(() =>
        requestAnimationFrame(() => b.classList.remove('cockpit--no-transition'))
      );
    }
  }

  function showSecuredIndicator() {
    if (!indicator) return;
    if (!indicator.dataset.normalContent)
      indicator.dataset.normalContent = indicator.textContent;
    indicator.textContent = 'SECURED';
    indicator.classList.add('cockpit-secured-pulse');
  }

  function hideSecuredIndicator() {
    if (!indicator) return;
    indicator.textContent = indicator.dataset.normalContent || '';
    indicator.classList.remove('cockpit-secured-pulse');
  }

  // ── Sequences ────────────────────────────────────────────────────────────

  function runShutdownSequence() {
    let stage = 0;
    function next() {
      stage++;
      applyStage(stage, false);
      if (stage < 4) {
        stageTimer = setTimeout(next, STAGE_DELAY);
      } else {
        secured = true;
        saveState();
        showSecuredIndicator();
        document.body.classList.add('cockpit--secured');
        stageTimer = null;
      }
    }
    stageTimer = setTimeout(next, STAGE_DELAY);
  }

  function runWakeSequence() {
    document.body.classList.remove('cockpit--secured');
    hideSecuredIndicator();
    let stage = 4;
    function prev() {
      stage--;
      if (stage > 0) {
        applyStage(stage, false);
        stageTimer = setTimeout(prev, STAGE_DELAY);
      } else {
        applyStage(0, false);
        secured = false; bank = null; progress = 0;
        saveState();
        stageTimer = null;
      }
    }
    stageTimer = setTimeout(prev, STAGE_DELAY);
  }

  // ── Switch logic ─────────────────────────────────────────────────────────

  function handleSwitchClick(sw) {
    if (stageTimer !== null) return; // sequence running — ignore all input

    if (!secured) {
      // Shutdown mode
      if (sw.step === 1 && bank === null) {
        bank = sw.bank; progress = 1;
        saveState();
      } else if (sw.bank === bank && sw.step === progress + 1) {
        progress++;
        saveState();
        if (progress === 4) runShutdownSequence();
      }
      // Wrong order/bank: silent

    } else {
      // Wake mode
      // Fallback: if bank lost, first step-4 claims it
      if (bank === null && sw.step === 4) {
        bank = sw.bank; progress = 4; saveState();
      }
      if (sw.bank === bank && sw.step === progress && progress > 0) {
        progress--;
        saveState();
        if (progress === 0) {
          bank = null; saveState();
          runWakeSequence();
        }
      }
      // Wrong order/bank: silent
    }
  }

  // ── Click zones ───────────────────────────────────────────────────────────

  function positionZone(sw) {
    const zone = document.getElementById('zone-' + sw.id);
    if (!zone) return;
    if (vintageSwitches()) {
      const col = (sw.step - 1) % 2;
      const row = Math.floor((sw.step - 1) / 2);
      const outer = document.querySelector?.(sw.bank === 'L' ? '.gauge-airlines' : '.gauge-airports');
      const bounds = outer?.getBoundingClientRect();
      const edge = window.innerWidth * (sw.bank === 'L' ? .08 : .92);
      const gaugeEdge = bounds ? (sw.bank === 'L' ? bounds.left : bounds.right) : window.innerWidth * (sw.bank === 'L' ? .212 : .792);
      const centre = (edge + gaugeEdge) / 2 / window.innerWidth * 100;
      const x = centre + (col ? 1.5 : -1.5);
      const y = 48 + row * 8;
      // switch patch 2a r2 (Bob 6737): at <=1199px keep the two columns at least 22px either side of centre
      // so the 36px buttons never overlap; wider screens keep the original 1.5% offset exactly.
      zone.style.left = window.innerWidth <= 1199
        ? `calc(${centre}% ${col ? '+' : '-'} max(1.5vw, 22px) - 18px)`
        : `calc(${x}% - 18px)`;
      zone.style.top = `${y}%`; zone.style.width = '36px'; zone.style.height = '42px';
      return;
    }
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const scale = Math.max(vw / BASE_W, vh / BASE_H);
    const ox = (vw - BASE_W * scale) / 2;
    const oy = (vh - BASE_H * scale) / 2;
    const cx = ox + sw.px * scale;
    const cy = oy + sw.py * scale;
    // switch patch 1: round targets sized to 95% of the nearest neighbour's distance (16-32px), so
    // neighbouring switches never overlap when the artwork is scaled down (L3/L4 are 29px apart at 1536px).
    const nearest = Math.min(...SWITCHES.filter(o => o !== sw).map(o => Math.hypot(o.px - sw.px, o.py - sw.py)));
    // switch patch 2b (Bob 6723/6728): aim for 24-32px; where neighbours are too close, push this centre away from
    // each of them by half the shortfall (+2px gap), capped at 4px in total. Over the cap, fall back to the
    // patch-1 shrink-to-fit size with no displacement.
    let s  = Math.max(24, Math.min(32, Math.floor(nearest * scale * 0.95)));
    let dx = 0, dy = 0;
    SWITCHES.forEach(o => {
      if (o === sw) return;
      const vx = (sw.px - o.px) * scale, vy = (sw.py - o.py) * scale, d = Math.hypot(vx, vy);
      if (d > 0 && d < s + 2) { const k = (s + 2 - d) / 2 / d; dx += vx * k; dy += vy * k; }
    });
    if (Math.hypot(dx, dy) > 4) { s = Math.max(16, Math.min(32, Math.floor(nearest * scale * 0.95))); dx = 0; dy = 0; }
    zone.dataset.offsetPx = Math.hypot(dx, dy).toFixed(1);
    zone.style.left   = (cx + dx - s / 2) + 'px';
    zone.style.top    = (cy + dy - s / 2) + 'px';
    zone.style.width  = s + 'px';
    zone.style.height = s + 'px';
  }

  function repositionAll() { SWITCHES.forEach(positionZone); }

  // ── Build DOM ────────────────────────────────────────────────────────────

  function buildClickZones() {
    const wrap = document.createElement('div');
    wrap.className = 'cockpit-click-zones';
    // switch patch 1: real buttons in every theme so the switches are reachable and operable by keyboard
    SWITCHES.forEach(sw => {
      const z = document.createElement('button');
      z.type = 'button'; z.dataset.label = sw.bank + sw.step;
      z.id = 'zone-' + sw.id;
      z.className = 'cockpit-click-zone';
      z.addEventListener('click', () => handleSwitchClick(sw));
      wrap.appendChild(z);
    });
    document.body.appendChild(wrap);
    repositionAll();
  }

  // ── Restore on load ───────────────────────────────────────────────────────

  function restoreState() {
    if (secured) {
      applyStage(4, true);
      document.body.classList.add('cockpit--secured');
      showSecuredIndicator();
    } else {
      // Clear any partial progress silently
      if (progress > 0 || bank !== null) {
        progress = 0; bank = null;
        saveState();
      }
    }
  }

  // ── Init ─────────────────────────────────────────────────────────────────

  function init() {
    loadState();
    buildClickZones();
    indicator = document.getElementById('radar-content');
    restoreState();
    updateSwitchVisuals();
    window.addEventListener('resize', repositionAll, { passive: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();

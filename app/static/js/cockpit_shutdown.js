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

  // ── Storage ──────────────────────────────────────────────────────────────

  function saveState() {
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
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const scale = Math.max(vw / BASE_W, vh / BASE_H);
    const ox = (vw - BASE_W * scale) / 2;
    const oy = (vh - BASE_H * scale) / 2;
    const cx = ox + sw.px * scale;
    const cy = oy + sw.py * scale;
    const s  = 32; // click target size px
    zone.style.left   = (cx - s / 2) + 'px';
    zone.style.top    = (cy - s / 2) + 'px';
    zone.style.width  = s + 'px';
    zone.style.height = s + 'px';
  }

  function repositionAll() { SWITCHES.forEach(positionZone); }

  // ── Build DOM ────────────────────────────────────────────────────────────

  function buildClickZones() {
    const wrap = document.createElement('div');
    wrap.className = 'cockpit-click-zones';
    wrap.setAttribute('aria-hidden', 'true');
    SWITCHES.forEach(sw => {
      const z = document.createElement('div');
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
    window.addEventListener('resize', repositionAll, { passive: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();

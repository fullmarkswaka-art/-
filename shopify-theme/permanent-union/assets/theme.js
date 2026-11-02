/* PERMANENT UNION theme JS — no dependencies */
(function () {
  'use strict';

  /* ---------- helpers ---------- */
  const $ = (s, c = document) => c.querySelector(s);
  const $$ = (s, c = document) => Array.from(c.querySelectorAll(s));
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const isSP = () => window.matchMedia('(max-width: 768px)').matches;

  function formatMoney(cents, format) {
    format = format || (window.theme && window.theme.moneyFormat) || '¥{{amount_no_decimals}}';
    const value = cents / 100;
    const m = format.match(/\{\{\s*(\w+)\s*\}\}/);
    const type = m ? m[1] : 'amount';
    let out;
    switch (type) {
      case 'amount_no_decimals': out = Math.round(value).toLocaleString('ja-JP'); break;
      case 'amount_with_comma_separator': out = value.toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '.'); break;
      case 'amount_no_decimals_with_comma_separator': out = Math.round(value).toLocaleString('de-DE'); break;
      default: out = value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return format.replace(/\{\{\s*\w+\s*\}\}/, out);
  }
  window.theme = window.theme || {};
  window.theme.formatMoney = formatMoney;

  function toast(msg) {
    let el = $('.toast');
    if (!el) { el = document.createElement('div'); el.className = 'toast'; document.body.appendChild(el); }
    el.textContent = msg;
    el.classList.add('is-visible');
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.remove('is-visible'), 2600);
  }

  /* ---------- reveal on scroll ---------- */
  function initReveal() {
    const els = $$('.reveal');
    if (!('IntersectionObserver' in window) || reduceMotion) { els.forEach(e => e.classList.add('is-visible')); return; }
    const io = new IntersectionObserver((entries) => {
      entries.forEach(en => { if (en.isIntersecting) { en.target.classList.add('is-visible'); io.unobserve(en.target); } });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
    els.forEach(e => io.observe(e));
  }

  /* ---------- header: color follows the section under it ---------- */
  function initHeader() {
    const hd = $('[data-header]');
    if (!hd) return;
    const def = hd.dataset.defaultMode || 'dark';
    const sections = $$('[data-header]').filter(el => el !== hd && el.dataset.header);
    const setMode = (m) => { hd.classList.toggle('hd--light', m === 'light'); hd.classList.toggle('hd--dark', m !== 'light'); };
    const onScroll = () => {
      hd.classList.toggle('is-scrolled', window.scrollY > 40);
      // the section whose box contains the header's vertical centre
      const y = 55;
      let mode = def;
      for (const el of sections) {
        const r = el.getBoundingClientRect();
        if (r.top <= y && r.bottom > y) { mode = el.dataset.header; break; }
      }
      setMode(mode);
    };
    onScroll();
    let ticking = false;
    window.addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(() => { onScroll(); ticking = false; }); } }, { passive: true });
    window.addEventListener('resize', onScroll);
  }

  /* ---------- drawers (menu / cart) ---------- */
  function openDrawer(id) {
    const d = document.getElementById(id);
    if (!d) return;
    d.classList.add('is-open');
    d.setAttribute('aria-hidden', 'false');
    document.body.classList.add('is-locked');
    $$('[data-drawer-open="' + id + '"]').forEach(b => b.setAttribute('aria-expanded', 'true'));
    const f = d.querySelector('button, a, input');
    if (f) setTimeout(() => f.focus(), 300);
  }
  function closeDrawers() {
    $$('.drawer.is-open, .menu.is-open').forEach(d => { d.classList.remove('is-open'); d.setAttribute('aria-hidden', 'true'); });
    $$('[data-drawer-open]').forEach(b => b.setAttribute('aria-expanded', 'false'));
    document.body.classList.remove('is-locked');
  }
  function initDrawers() {
    document.addEventListener('click', (e) => {
      const open = e.target.closest('[data-drawer-open]');
      if (open) { e.preventDefault(); closeDrawers(); openDrawer(open.dataset.drawerOpen); return; }
      if (e.target.closest('[data-drawer-close]')) { e.preventDefault(); closeDrawers(); }
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDrawers(); });
  }
  window.theme.openDrawer = openDrawer;
  window.theme.closeDrawers = closeDrawers;

  /* ---------- cart (AJAX) ---------- */
  async function fetchCart() {
    const r = await fetch(window.theme.routes.cart_url + '.js', { headers: { Accept: 'application/json' } });
    return r.json();
  }
  async function refreshCartDrawer() {
    const drawer = $('#CartDrawer');
    if (!drawer) return;
    const r = await fetch(window.location.pathname + '?section_id=cart-drawer');
    const html = await r.text();
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const fresh = doc.querySelector('#CartDrawer');
    if (fresh) { const wasOpen = drawer.classList.contains('is-open'); drawer.innerHTML = fresh.innerHTML; if (wasOpen) drawer.classList.add('is-open'); }
  }
  function updateCounts(cart) {
    $$('[data-cart-count]').forEach(el => { el.textContent = cart.item_count; el.hidden = cart.item_count === 0; });
  }
  async function addToCart(form) {
    const btn = form.querySelector('[type="submit"]');
    const fd = new FormData(form);
    if (btn) btn.disabled = true;
    try {
      const r = await fetch(window.theme.routes.cart_add_url + '.js', { method: 'POST', body: fd, headers: { Accept: 'application/json' } });
      const data = await r.json();
      if (!r.ok) { toast(data.description || window.theme.strings.cartError); return; }
      const cart = await fetchCart();
      updateCounts(cart);
      if (document.body.dataset.cartType === 'drawer' && $('#CartDrawer')) {
        await refreshCartDrawer();
        openDrawer('CartDrawer');
      } else {
        window.location.href = window.theme.routes.cart_url;
      }
    } catch (err) { toast(window.theme.strings.cartError); }
    finally { if (btn) btn.disabled = false; }
  }
  async function changeLine(line, quantity) {
    const r = await fetch(window.theme.routes.cart_change_url + '.js', {
      method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ line, quantity })
    });
    const cart = await r.json();
    updateCounts(cart);
    if ($('#CartDrawer') && $('#CartDrawer').classList.contains('is-open')) {
      await refreshCartDrawer();
    } else if (document.body.classList.contains('template-cart')) {
      window.location.reload();
    }
  }
  function initCart() {
    document.addEventListener('submit', (e) => {
      const form = e.target.closest('form[data-ajax-cart]');
      if (!form || form.dataset.ajaxCart === 'false') return;
      e.preventDefault();
      addToCart(form);
    });
    document.addEventListener('click', (e) => {
      const qb = e.target.closest('[data-qty-change]');
      if (qb) {
        const input = qb.parentElement.querySelector('input');
        const min = parseInt(input.min || '1', 10);
        let v = parseInt(input.value || '1', 10) + parseInt(qb.dataset.qtyChange, 10);
        if (v < min) v = min;
        input.value = v;
        input.dispatchEvent(new Event('change', { bubbles: true }));
        return;
      }
      const rm = e.target.closest('[data-line-remove]');
      if (rm) { e.preventDefault(); changeLine(parseInt(rm.dataset.lineRemove, 10), 0); }
    });
    document.addEventListener('change', (e) => {
      const input = e.target.closest('[data-line-qty]');
      if (input) changeLine(parseInt(input.dataset.lineQty, 10), parseInt(input.value, 10));
    });
  }

  /* ---------- product: variants, stock states, gallery, sticky button ---------- */
  class ProductForm {
    constructor(root) {
      this.root = root;
      const jsonEl = root.querySelector('[data-product-json]');
      if (!jsonEl) return;
      this.product = JSON.parse(jsonEl.textContent);
      this.form = root.querySelector('form[data-product-form]');
      if (!this.form) return;
      this.idInput = this.form.querySelector('input[name="id"]');
      this.priceEl = root.querySelector('[data-price]');
      this.btn = this.form.querySelector('[data-add-button]');
      this.btnText = this.btn.querySelector('span');
      this.addPrices = $$('[data-add-price]', root);
      this.stockMsg = root.querySelector('[data-stock-msg]');
      this.low = window.theme.lowStock || 3;
      root.addEventListener('change', (e) => { if (e.target.matches('[data-option-input]')) this.onChange(); });
      this.onChange(true);
      this.initGallery();
      this.initSticky();
    }
    selectedOptions() {
      return $$('[data-option-index]', this.root).map(fs => { const c = fs.querySelector('input:checked'); return c ? c.value : null; });
    }
    findVariant(opts) {
      return this.product.variants.find(v => v.options.every((o, i) => o === opts[i]));
    }
    onChange(initial) {
      const opts = this.selectedOptions();
      const variant = this.findVariant(opts);
      this.updateAvailability(opts);
      $$('[data-option-index]', this.root).forEach((fs, i) => { const b = fs.querySelector('[data-option-value]'); if (b) b.textContent = opts[i] || ''; });
      if (!variant) {
        this.btn.disabled = true; this.btnText.textContent = window.theme.strings.unavailable;
        if (this.stockMsg) this.stockMsg.hidden = true;
        return;
      }
      this.idInput.value = variant.id;
      const price = formatMoney(variant.price);
      if (this.priceEl) {
        const cmp = variant.compare_at_price && variant.compare_at_price > variant.price ? '<s class="pd__compare">' + formatMoney(variant.compare_at_price) + '</s>' : '';
        this.priceEl.innerHTML = cmp + '<span class="pd__amount">' + price + '</span><span class="pd__tax">' + (this.priceEl.dataset.taxLabel || '') + '</span>';
      }
      this.addPrices.forEach(el => { el.textContent = price; });
      this.btn.disabled = !variant.available;
      this.btnText.textContent = variant.available ? window.theme.strings.addToCart : window.theme.strings.soldOut;
      $$('[data-sticky-button]', this.root).forEach(b => { b.disabled = !variant.available; b.querySelector('span').textContent = this.btnText.textContent; });
      if (this.stockMsg) {
        const q = variant.inventory_quantity;
        const tracked = variant.inventory_management;
        if (variant.available && tracked && typeof q === 'number' && q > 0 && q <= this.low) { this.stockMsg.textContent = window.theme.strings.lowStock + '（' + q + '）'; this.stockMsg.hidden = false; }
        else { this.stockMsg.hidden = true; }
      }
      if (!initial) {
        const url = new URL(window.location); url.searchParams.set('variant', variant.id); history.replaceState({}, '', url);
      }
      if (variant.featured_media && this.main) {
        const m = this.main.querySelector('[data-media-id="' + variant.featured_media.id + '"]');
        if (m && !initial) this.showSlide(m);
      }
    }
    // mark each size/colour as sold out or low stock relative to the other selected options
    updateAvailability(opts) {
      $$('[data-option-index]', this.root).forEach((fs, idx) => {
        $$('input[data-option-input]', fs).forEach(input => {
          const test = opts.slice(); test[idx] = input.value;
          const matches = this.product.variants.filter(v => v.options.every((o, i) => i === idx ? o === test[idx] : (test[i] == null || o === test[i])));
          const available = matches.some(v => v.available);
          const label = fs.querySelector('label[for="' + input.id + '"]');
          if (!label) return;
          label.classList.toggle('is-out', !available);
          const lowEl = label.querySelector('.sz__low');
          if (lowEl) {
            const qty = matches.filter(v => v.available && v.inventory_management).reduce((s, v) => s + (typeof v.inventory_quantity === 'number' ? v.inventory_quantity : 99), 0);
            const tracked = matches.some(v => v.inventory_management);
            lowEl.hidden = !(available && tracked && qty > 0 && qty <= this.low);
          }
        });
      });
    }
    initGallery() {
      this.main = this.root.querySelector('[data-gallery-main]');
      if (!this.main) return;
      const slides = $$('.pd__slide', this.main);
      const thumbs = $$('[data-thumb]', this.root);
      const dots = $$('[data-gallery-dots] span', this.root);
      const setActive = (i) => {
        thumbs.forEach((t, k) => t.classList.toggle('is-on', k === i));
        dots.forEach((d, k) => d.classList.toggle('is-on', k === i));
      };
      thumbs.forEach((t, i) => t.addEventListener('click', () => this.showSlide(slides[i])));
      if (isSP()) {
        // horizontal snap on SP
        let tk = false;
        this.main.addEventListener('scroll', () => {
          if (tk) return; tk = true;
          requestAnimationFrame(() => { setActive(Math.round(this.main.scrollLeft / this.main.clientWidth)); tk = false; });
        }, { passive: true });
      } else if ('IntersectionObserver' in window) {
        const io = new IntersectionObserver((ens) => { ens.forEach(en => { if (en.isIntersecting) setActive(slides.indexOf(en.target)); }); }, { root: this.main, threshold: 0.6 });
        slides.forEach(s => io.observe(s));
      }
    }
    showSlide(el) {
      if (!el || !this.main) return;
      if (isSP()) this.main.scrollTo({ left: el.offsetLeft, behavior: reduceMotion ? 'auto' : 'smooth' });
      else this.main.scrollTo({ top: el.offsetTop, behavior: reduceMotion ? 'auto' : 'smooth' });
    }
    initSticky() {
      const bar = this.root.querySelector('[data-sticky-add]');
      if (!bar || !('IntersectionObserver' in window)) return;
      const io = new IntersectionObserver((ens) => { ens.forEach(en => { const show = !en.isIntersecting && en.boundingClientRect.top < 0; bar.classList.toggle('is-visible', show); bar.setAttribute('aria-hidden', show ? 'false' : 'true'); }); }, { threshold: 0 });
      io.observe(this.btn);
      bar.querySelector('[data-sticky-button]').addEventListener('click', () => {
        if (this.btn.disabled) { this.form.scrollIntoView({ behavior: 'smooth', block: 'center' }); return; }
        if (this.form.dataset.ajaxCart === 'false') this.form.submit(); else addToCart(this.form);
      });
    }
  }
  function initProductForms() { $$('[data-product]').forEach(el => new ProductForm(el)); }

  /* ---------- related products (Section Rendering API) ---------- */
  function initRelated() {
    const el = $('[data-related]');
    if (!el || !el.dataset.url) return;
    fetch(el.dataset.url).then(r => r.text()).then(html => {
      const doc = new DOMParser().parseFromString(html, 'text/html');
      const fresh = doc.querySelector('[data-related] .cards');
      if (fresh && fresh.children.length) el.querySelector('.cards').innerHTML = fresh.innerHTML;
    }).catch(() => {});
  }

  /* ---------- opening: logo fade in → hold → fade out (once per session) ---------- */
  function initOpening() {
    const op = $('[data-opening]');
    if (!op) return;
    let seen = false;
    try { seen = sessionStorage.getItem('pu_opening_seen') === '1'; } catch (e) {}
    if (seen || reduceMotion) { op.remove(); return; }
    try { sessionStorage.setItem('pu_opening_seen', '1'); } catch (e) {}
    const fin = parseFloat(op.dataset.fadeIn || 0.8) * 1000, hold = parseFloat(op.dataset.hold || 1.2) * 1000, fout = parseFloat(op.dataset.fadeOut || 0.8) * 1000;
    op.style.setProperty('--op-in', fin + 'ms'); op.style.setProperty('--op-out', fout + 'ms');
    document.body.classList.add('is-opening');
    op.classList.add('is-active');
    let done = false;
    const end = () => {
      if (done) return; done = true;
      op.classList.add('is-leaving');
      document.body.classList.remove('is-opening');
      setTimeout(() => op.remove(), fout + 50);
      ['click', 'wheel', 'touchstart', 'keydown'].forEach(ev => window.removeEventListener(ev, end));
    };
    ['click', 'wheel', 'touchstart', 'keydown'].forEach(ev => window.addEventListener(ev, end, { passive: true }));
    setTimeout(() => op.classList.add('is-logo'), 50);
    setTimeout(end, fin + hold + 100);
  }

  /* ---------- first view: photo drifts up & fades with scroll ---------- */
  function initFirstView() {
    const fv = $('[data-fv]');
    if (!fv) return;
    const photo = fv.querySelector('[data-fv-photo]');
    const update = () => {
      const h = fv.offsetHeight || window.innerHeight;
      const p = Math.min(Math.max(window.scrollY / h, 0), 1);
      photo.style.setProperty('--p', p.toFixed(3));
    };
    if (reduceMotion) return;
    update();
    let tk = false;
    window.addEventListener('scroll', () => { if (!tk) { tk = true; requestAnimationFrame(() => { update(); tk = false; }); } }, { passive: true });
  }

  /* ---------- story: light parallax + chapter indicator ---------- */
  function initStories() {
    const stories = $$('[data-story]');
    const ind = $('[data-indicator]');
    if (!stories.length) { if (ind) ind.remove(); return; }
    const segs = ind ? $$('[data-seg]', ind) : [];
    const label = ind ? ind.querySelector('[data-indicator-label]') : null;
    const setChapter = (st) => {
      if (!ind) return;
      if (!st) { ind.classList.remove('is-on'); segs.forEach(s => s.classList.remove('is-on')); if (label) label.textContent = ''; return; }
      ind.classList.add('is-on');
      const n = parseInt(st.dataset.chapter, 10);
      segs.forEach(s => { const on = parseInt(s.dataset.seg, 10) === n; s.classList.toggle('is-on', on); if (on) s.style.setProperty('--seg-color', st.dataset.chapterColor || '#fff'); });
      if (label) label.textContent = st.dataset.chapterName || '';
    };
    const update = () => {
      const mid = window.innerHeight * 0.5;
      let current = null;
      for (const st of stories) {
        const r = st.getBoundingClientRect();
        if (r.top <= mid && r.bottom >= mid) { current = st; }
        if (!reduceMotion) {
          const media = st.querySelector('[data-parallax].story__media--parallax');
          if (media && r.bottom > 0 && r.top < window.innerHeight) {
            const prog = (r.top + r.height / 2 - mid) / (window.innerHeight + r.height); // -0.5 .. 0.5
            media.style.setProperty('--py', (prog * -16).toFixed(2) + '%');
          }
        }
      }
      setChapter(current);
      // hide the indicator once we've scrolled past the story area into the paper sections
      if (ind) { const last = stories[stories.length - 1].getBoundingClientRect(); ind.classList.toggle('is-hidden', last.bottom < 0 || window.scrollY < 10); }
    };
    update();
    let tk = false;
    window.addEventListener('scroll', () => { if (!tk) { tk = true; requestAnimationFrame(() => { update(); tk = false; }); } }, { passive: true });
    window.addEventListener('resize', update);
  }

  /* ---------- background video ---------- */
  function initVideos() {
    $$('video[autoplay]').forEach(v => {
      if (reduceMotion) { v.pause(); v.removeAttribute('autoplay'); return; }
      v.muted = true; const p = v.play(); if (p && p.catch) p.catch(() => {});
    });
  }

  /* ---------- collection: sort & facets ---------- */
  function initCollection() {
    const sort = $('[data-sort-by]');
    if (sort) sort.addEventListener('change', () => {
      const url = new URL(window.location); url.searchParams.set('sort_by', sort.value); url.searchParams.delete('page'); window.location = url;
    });
    const toggle = $('[data-facets-toggle]');
    const facets = $('[data-facet-form]');
    if (toggle && facets) toggle.addEventListener('click', () => { const open = facets.classList.toggle('is-open'); toggle.setAttribute('aria-expanded', open ? 'true' : 'false'); });
  }

  /* ---------- shop list: pins on the map, hover card, region tabs ---------- */
  function initShoplist() {
    const root = $('[data-shoplist]');
    if (!root) return;
    const wrap = root.querySelector('[data-map]');
    const svg = wrap && wrap.querySelector('svg');
    const card = root.querySelector('[data-shopcard]');
    const rows = $$('[data-shop]', root.querySelector('[data-shop-list]'));
    const pins = $$('.pin', wrap);
    const rowFor = (id) => rows.find(r => r.dataset.shop === id);

    // place pins at the centre of each prefecture
    const place = () => {
      if (!svg) return;
      const wb = wrap.getBoundingClientRect();
      pins.forEach(pin => {
        let el = svg.querySelector('[data-code="' + pin.dataset.pin + '"]');
        if (!el) { pin.hidden = true; return; }
        if (el.querySelector('path')) el = el.querySelector('path');
        const r = el.getBoundingClientRect();
        pin.style.left = ((r.left + r.width / 2 - wb.left) / wb.width * 100).toFixed(2) + '%';
        pin.style.top = ((r.top + r.height / 2 - wb.top) / wb.height * 100).toFixed(2) + '%';
      });
    };
    place();
    window.addEventListener('resize', place);
    // highlight prefectures with shops
    pins.forEach(p => { const el = svg && svg.querySelector('[data-code="' + p.dataset.pin + '"]'); if (el) el.classList.add('has-shop'); });

    const showCard = (id, pin) => {
      const row = rowFor(id);
      if (!row || !card) return;
      card.querySelector('[data-card-region]').textContent = row.dataset.area || '';
      card.querySelector('[data-card-name]').textContent = row.dataset.name || '';
      card.querySelector('[data-card-meta]').innerHTML = [row.dataset.address, row.dataset.tel, row.dataset.hours].filter(Boolean).join('<br>');
      const links = [];
      if (row.dataset.map) links.push('<a href="' + row.dataset.map + '" target="_blank" rel="noopener">MAP ↗</a>');
      if (row.dataset.web) links.push('<a href="' + row.dataset.web + '" target="_blank" rel="noopener">WEB ↗</a>');
      card.querySelector('[data-card-links]').innerHTML = links.join('　／　');
      const ph = card.querySelector('[data-card-photo]');
      if (row.dataset.photo) { ph.innerHTML = '<img src="' + row.dataset.photo + '" alt="">'; ph.hidden = false; } else { ph.innerHTML = ''; ph.hidden = true; }
      card.hidden = false;
      pins.forEach(p => p.classList.toggle('is-on', p === pin));
      rows.forEach(r => r.classList.toggle('is-on', r === row));
      if (pin && !isSP()) {
        // position the card beside the pin (inside the map box)
        const wb = wrap.getBoundingClientRect(); const pr = pin.getBoundingClientRect();
        let left = pr.left - wb.left + 18, top = pr.top - wb.top - 20;
        if (left + 260 > wb.width) left = pr.left - wb.left - 270;
        if (top + 200 > wb.height) top = wb.height - 200;
        card.style.left = Math.max(0, left) + 'px'; card.style.top = Math.max(0, top) + 'px';
      } else { card.style.left = ''; card.style.top = ''; }
    };
    pins.forEach(pin => {
      pin.addEventListener('mouseenter', () => showCard(pin.dataset.shop, pin));
      pin.addEventListener('focus', () => showCard(pin.dataset.shop, pin));
      pin.addEventListener('click', () => { showCard(pin.dataset.shop, pin); const row = rowFor(pin.dataset.shop); if (row && isSP()) row.scrollIntoView({ behavior: 'smooth', block: 'center' }); });
    });
    rows.forEach(row => row.addEventListener('mouseenter', () => showCard(row.dataset.shop, pins.find(p => p.dataset.shop === row.dataset.shop))));
    // default: first shop
    if (pins[0]) showCard(pins[0].dataset.shop, pins[0]);

    // region tabs
    $$('[data-region]', root.querySelector('.tabs--regions')).forEach(tab => tab.addEventListener('click', () => {
      const id = tab.dataset.region;
      $$('.tab', tab.parentElement).forEach(t => t.classList.toggle('is-on', t === tab));
      rows.forEach(r => { r.hidden = id !== 'all' && r.dataset.region !== id; });
      $$('[data-region-head]', root).forEach(h => { h.hidden = id !== 'all' && h.dataset.regionHead !== id; });
      pins.forEach(p => { p.classList.toggle('is-dim', id !== 'all' && p.dataset.region !== id); });
    }));
  }

  /* ---------- guide: highlight the current section in the TOC ---------- */
  function initGuide() {
    const root = $('[data-guide]');
    if (!root || !('IntersectionObserver' in window)) return;
    const links = $$('[data-toc]', root);
    const io = new IntersectionObserver((ens) => {
      ens.forEach(en => { if (en.isIntersecting) links.forEach(l => l.classList.toggle('is-on', l.getAttribute('href') === '#' + en.target.id)); });
    }, { rootMargin: '-30% 0px -60% 0px' });
    $$('.guide__sec', root).forEach(s => io.observe(s));
  }

  document.addEventListener('DOMContentLoaded', () => {
    initOpening(); initReveal(); initHeader(); initDrawers(); initCart(); initProductForms(); initRelated();
    initVideos(); initFirstView(); initStories(); initCollection(); initShoplist(); initGuide();
  });
  // Shopify theme editor: re-init when a section is re-rendered
  document.addEventListener('shopify:section:load', () => { initReveal(); initProductForms(); initShoplist(); initStories(); });
})();

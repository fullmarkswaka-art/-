/* PERMANENT UNION theme JS — no dependencies */
(function () {
  'use strict';

  /* ---------- helpers ---------- */
  const $ = (s, c = document) => c.querySelector(s);
  const $$ = (s, c = document) => Array.from(c.querySelectorAll(s));

  function formatMoney(cents, format) {
    format = format || (window.theme && window.theme.moneyFormat) || '¥{{amount_no_decimals}}';
    const value = (cents / 100);
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
    if (!('IntersectionObserver' in window)) { els.forEach(e => e.classList.add('is-visible')); return; }
    const io = new IntersectionObserver((entries) => {
      entries.forEach(en => { if (en.isIntersecting) { en.target.classList.add('is-visible'); io.unobserve(en.target); } });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });
    els.forEach(e => io.observe(e));
  }

  /* ---------- header ---------- */
  function initHeader() {
    const wrap = $('.header-wrap');
    if (!wrap) return;
    let last = window.scrollY;
    const onScroll = () => {
      const y = window.scrollY;
      wrap.classList.toggle('is-scrolled', y > 40);
      if (wrap.dataset.hideOnScroll === 'true') {
        wrap.classList.toggle('is-hidden', y > last && y > 240);
      }
      last = y;
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }

  /* ---------- drawers ---------- */
  function openDrawer(id) {
    const d = document.getElementById(id);
    if (!d) return;
    d.classList.add('is-open');
    d.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    const f = d.querySelector('button, a, input');
    if (f) setTimeout(() => f.focus(), 300);
  }
  function closeDrawers() {
    $$('.drawer.is-open').forEach(d => { d.classList.remove('is-open'); d.setAttribute('aria-hidden', 'true'); });
    document.body.style.overflow = '';
  }
  function initDrawers() {
    document.addEventListener('click', (e) => {
      const open = e.target.closest('[data-drawer-open]');
      if (open) { e.preventDefault(); openDrawer(open.dataset.drawerOpen); return; }
      if (e.target.closest('[data-drawer-close]') || e.target.classList.contains('drawer__backdrop')) { closeDrawers(); }
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDrawers(); });
  }
  window.theme.openDrawer = openDrawer;
  window.theme.closeDrawers = closeDrawers;

  /* ---------- cart ---------- */
  async function fetchCart() {
    const r = await fetch(window.theme.routes.cart_url + '.js', { headers: { 'Accept': 'application/json' } });
    return r.json();
  }
  async function refreshCartDrawer() {
    const drawer = $('#CartDrawer');
    if (!drawer) return;
    const r = await fetch(window.location.pathname + '?section_id=cart-drawer');
    const html = await r.text();
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const fresh = doc.querySelector('#CartDrawer');
    if (fresh) drawer.innerHTML = fresh.innerHTML;
  }
  function updateCounts(cart) {
    $$('[data-cart-count]').forEach(el => { el.textContent = cart.item_count; el.hidden = cart.item_count === 0; });
  }
  async function addToCart(form) {
    const btn = form.querySelector('[type="submit"]');
    const fd = new FormData(form);
    btn.disabled = true;
    try {
      const r = await fetch(window.theme.routes.cart_add_url + '.js', { method: 'POST', body: fd, headers: { 'Accept': 'application/json' } });
      const data = await r.json();
      if (!r.ok) { toast(data.description || window.theme.strings.cartError); return; }
      const cart = await fetchCart();
      updateCounts(cart);
      if (document.body.dataset.cartType === 'drawer' && $('#CartDrawer')) {
        await refreshCartDrawer();
        openDrawer('CartDrawer');
      } else if (document.body.dataset.cartType === 'page') {
        window.location.href = window.theme.routes.cart_url;
      } else {
        toast(window.theme.strings.addedToCart);
      }
    } catch (err) { toast(window.theme.strings.cartError); }
    finally { btn.disabled = false; }
  }
  async function changeLine(line, quantity) {
    const r = await fetch(window.theme.routes.cart_change_url + '.js', {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
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

  /* ---------- product form / variants ---------- */
  class ProductForm {
    constructor(root) {
      this.root = root;
      const jsonEl = root.querySelector('[data-product-json]');
      if (!jsonEl) return;
      this.product = JSON.parse(jsonEl.textContent);
      this.form = root.querySelector('form[data-product-form]');
      this.idInput = this.form.querySelector('input[name="id"]');
      this.priceEl = root.querySelector('[data-price]');
      this.btn = this.form.querySelector('[data-add-button]');
      this.btnText = this.btn.querySelector('span');
      this.gallery = root.querySelector('[data-gallery]');
      root.addEventListener('change', (e) => { if (e.target.matches('[data-option-input]')) this.onChange(); });
      this.onChange(true);
    }
    selectedOptions() {
      const opts = [];
      this.root.querySelectorAll('[data-option-index]').forEach(fs => {
        const checked = fs.querySelector('input:checked') || fs.querySelector('select');
        opts.push(checked ? checked.value : null);
      });
      return opts;
    }
    onChange(initial) {
      const opts = this.selectedOptions();
      const variant = this.product.variants.find(v => v.options.every((o, i) => o === opts[i]));
      this.updateAvailability(opts);
      if (!variant) {
        this.btn.disabled = true; this.btnText.textContent = window.theme.strings.unavailable; return;
      }
      this.idInput.value = variant.id;
      if (this.priceEl) {
        let html = '';
        if (variant.compare_at_price && variant.compare_at_price > variant.price) {
          html = '<span class="price price--sale"><span class="price__regular">' + formatMoney(variant.compare_at_price) + '</span>' + formatMoney(variant.price) + '</span>';
        } else { html = '<span class="price">' + formatMoney(variant.price) + '</span>'; }
        this.priceEl.innerHTML = html + '<span class="price__unit">' + (this.priceEl.dataset.taxLabel || '') + '</span>';
      }
      this.btn.disabled = !variant.available;
      this.btnText.textContent = variant.available ? window.theme.strings.addToCart : window.theme.strings.soldOut;
      this.root.querySelectorAll('[data-option-index]').forEach((fs, i) => {
        const b = fs.querySelector('[data-option-value]'); if (b) b.textContent = opts[i];
      });
      if (!initial) {
        const url = new URL(window.location); url.searchParams.set('variant', variant.id); history.replaceState({}, '', url);
      }
      if (variant.featured_media && this.gallery) {
        const m = this.gallery.querySelector('[data-media-id="' + variant.featured_media.id + '"]');
        if (m && !initial) m.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' });
      }
    }
    updateAvailability(opts) {
      const fieldsets = this.root.querySelectorAll('[data-option-index]');
      fieldsets.forEach((fs, idx) => {
        fs.querySelectorAll('input[data-option-input]').forEach(input => {
          const test = opts.slice(); test[idx] = input.value;
          const match = this.product.variants.find(v => v.options.every((o, i) => i === idx ? o === test[idx] : (test[i] == null || o === test[i])));
          const label = fs.querySelector('label[for="' + input.id + '"]');
          if (label) label.classList.toggle('is-unavailable', !(match && match.available));
        });
      });
    }
  }
  function initProductForms() { $$('[data-product]').forEach(el => new ProductForm(el)); }

  /* ---------- hero video: ensure autoplay ---------- */
  function initVideos() {
    $$('video[autoplay]').forEach(v => { v.muted = true; const p = v.play(); if (p && p.catch) p.catch(() => {}); });
  }

  /* ---------- collection ---------- */
  function initCollection() {
    const sort = $('[data-sort-by]');
    if (sort) sort.addEventListener('change', () => {
      const url = new URL(window.location); url.searchParams.set('sort_by', sort.value); url.searchParams.delete('page'); window.location = url;
    });
    const facetForm = $('[data-facet-form]');
    if (facetForm) facetForm.addEventListener('change', () => facetForm.submit());
    const toggle = $('[data-facets-toggle]');
    if (toggle) toggle.addEventListener('click', () => $('.facets').classList.toggle('is-open'));
  }

  document.addEventListener('DOMContentLoaded', () => {
    initReveal(); initHeader(); initDrawers(); initCart(); initProductForms(); initVideos(); initCollection();
  });
})();

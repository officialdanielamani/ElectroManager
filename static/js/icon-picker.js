/* Canonical Bootstrap Icon Picker — used across the entire application.
 * API: IconPicker.open(callback, currentIcon)
 *   callback(iconClass) — called with e.g. 'bi-circle-fill' when user picks
 *   currentIcon        — optional, e.g. 'bi-circle-fill', highlights that icon
 *
 * Lazy rendering: icons are added in batches of PAGE_SIZE as the user scrolls,
 * keeping the initial paint fast regardless of catalogue size.
 */
(function () {
    'use strict';

    var PAGE_SIZE = 60;
    var _cache    = null;
    var _callback = null;
    var _selected = '';
    var _filtered = [];
    var _page     = 0;
    var _observer = null;

    function _esc(s) {
        return String(s || '').replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function open(callback, currentIcon) {
        _callback = callback || null;
        _selected = (currentIcon || '').replace(/^bi-/, '');
        var el = document.getElementById('iconPickerModal');
        if (!el) return;
        // Clear search so the picker opens at the beginning
        var searchEl = document.getElementById('iconPickerSearch');
        if (searchEl) searchEl.value = '';
        var modal = bootstrap.Modal.getOrCreateInstance(el);
        modal.show();
        if (!_cache) _load(); else _render();
    }

    async function _load() {
        var grid = document.getElementById('iconPickerGrid');
        if (grid) grid.innerHTML = '<p class="text-muted text-center py-4">Loading…</p>';
        try {
            var r = await fetch('/api/icons');
            _cache = await r.json();
            _render();
        } catch (e) {
            if (grid) grid.innerHTML = '<p class="text-danger text-center py-4">Error loading icons.</p>';
        }
    }

    function _disconnectObserver() {
        if (_observer) { _observer.disconnect(); _observer = null; }
    }

    function _render() {
        var grid = document.getElementById('iconPickerGrid');
        if (!grid || !_cache) return;
        var q = ((document.getElementById('iconPickerSearch') || {}).value || '').toLowerCase();
        _filtered = q ? _cache.filter(function (ic) { return ic.name.includes(q); }) : _cache;
        _page = 0;
        _disconnectObserver();
        grid.innerHTML = '';
        _appendBatch(grid);
    }

    function _appendBatch(grid) {
        if (!grid) grid = document.getElementById('iconPickerGrid');
        if (!grid || !_filtered) return;
        var start = _page * PAGE_SIZE;
        var batch = _filtered.slice(start, start + PAGE_SIZE);
        if (batch.length === 0) {
            if (_page === 0) {
                grid.innerHTML = '<p class="text-muted text-center py-4" style="grid-column:1/-1">No icons found.</p>';
            }
            return;
        }
        // Remove existing sentinel before appending
        var oldSentinel = document.getElementById('iconPickerSentinel');
        if (oldSentinel) oldSentinel.remove();

        var frag = document.createDocumentFragment();
        batch.forEach(function (ic) {
            var div = document.createElement('div');
            var sel = ic.name === _selected ? ' selected' : '';
            div.className = 'icon-opt js-pick-icon' + sel;
            div.dataset.icon = 'bi-' + ic.name;
            div.title = ic.name;
            div.innerHTML = '<i class="bi bi-' + _esc(ic.name) + '"></i><small>' + _esc(ic.name) + '</small>';
            frag.appendChild(div);
        });
        grid.appendChild(frag);
        _page++;

        // If more icons remain, attach a sentinel and observe it
        if (_page * PAGE_SIZE < _filtered.length) {
            var sentinel = document.createElement('div');
            sentinel.id = 'iconPickerSentinel';
            sentinel.style.cssText = 'grid-column:1/-1;height:1px;';
            grid.appendChild(sentinel);
            _disconnectObserver();
            _observer = new IntersectionObserver(function (entries) {
                if (entries[0].isIntersecting) _appendBatch(grid);
            }, { root: grid, threshold: 0 });
            _observer.observe(sentinel);
        }
    }

    function _pick(iconClass) {
        _selected = iconClass.replace(/^bi-/, '');
        _disconnectObserver();
        if (_callback) { _callback(iconClass); _callback = null; }
        var inst = bootstrap.Modal.getInstance(document.getElementById('iconPickerModal'));
        if (inst) inst.hide();
    }

    document.addEventListener('DOMContentLoaded', function () {
        var searchEl = document.getElementById('iconPickerSearch');
        if (searchEl) searchEl.addEventListener('input', _render);

        document.body.addEventListener('click', function (e) {
            var opt = e.target.closest('.js-pick-icon');
            if (opt) _pick(opt.dataset.icon);
        });

        // When the icon picker closes, restore modal-open on body so any
        // parent modal (card modal, column modal, etc.) remains usable.
        var pickerEl = document.getElementById('iconPickerModal');
        if (pickerEl) {
            pickerEl.addEventListener('hidden.bs.modal', function () {
                var anyOpen = document.querySelector('.modal.show');
                if (anyOpen) document.body.classList.add('modal-open');
            });
        }
    });

    window.IconPicker = { open: open };
})();

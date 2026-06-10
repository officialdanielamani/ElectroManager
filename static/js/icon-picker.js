/* Canonical Bootstrap Icon Picker — used across the entire application.
 * API: IconPicker.open(callback, currentIcon)
 *   callback(iconClass) — called with e.g. 'bi-circle-fill' when user picks
 *   currentIcon        — optional, e.g. 'bi-circle-fill', highlights that icon
 */
(function () {
    'use strict';

    var _cache = null;
    var _callback = null;
    var _selected = '';

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

    function _render() {
        var grid = document.getElementById('iconPickerGrid');
        if (!grid || !_cache) return;
        var q = (document.getElementById('iconPickerSearch') && document.getElementById('iconPickerSearch').value || '').toLowerCase();
        var filtered = q ? _cache.filter(function (ic) { return ic.name.includes(q); }) : _cache;
        var visible = q ? filtered : filtered.slice(0, 240);
        var html = visible.map(function (ic) {
            var sel = ic.name === _selected ? ' selected' : '';
            return '<div class="icon-opt js-pick-icon' + sel + '" data-icon="bi-' + _esc(ic.name) + '" title="' + _esc(ic.name) + '">' +
                '<i class="bi bi-' + _esc(ic.name) + '"></i>' +
                '<small>' + _esc(ic.name) + '</small>' +
                '</div>';
        }).join('');
        if (!q && filtered.length > 240) {
            html += '<p class="text-muted text-center py-2 small" style="grid-column:1/-1">Showing 240 of ' + filtered.length + ' — search to filter</p>';
        }
        grid.innerHTML = html || '<p class="text-muted text-center py-4" style="grid-column:1/-1">No icons found.</p>';
    }

    function _pick(iconClass) {
        _selected = iconClass.replace(/^bi-/, '');
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
    });

    window.IconPicker = { open: open };
})();

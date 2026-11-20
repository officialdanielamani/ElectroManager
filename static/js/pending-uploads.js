/* Files chosen in a New / Edit form are kept in the browser until the form is saved.
 *
 * Markup (one per upload area):
 *   <div class="pending-uploads" data-form="itemForm" data-name="new_attachments"
 *        data-rules='{"allowed":["pdf","png"],"maxBytes":10485760,"maxFiles":5,"existing":2}'
 *        data-existing=".existing-file[data-area='item']"></div>
 *
 * The browser checks type, size, count and whether the content matches the extension, shows
 * previews, and puts the accepted files into a hidden <input type=file> that is submitted
 * with the form. The server checks everything again (uploads.py).
 *
 * Existing files listed elsewhere on the page count towards the limit unless they carry the
 * class "pu-removing" (marked for removal); fire a "pending-uploads:recount" event on document
 * after changing that.
 */
(function () {
    'use strict';

    var IMAGE_EXTS = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'];
    var TEXT_EXTS = ['txt', 'md', 'csv', 'log', 'py', 'cpp', 'c', 'h', 'ino', 'json', 'xml', 'yaml', 'yml'];
    var SIGNATURES = {
        jpg: [[0xff, 0xd8, 0xff]], jpeg: [[0xff, 0xd8, 0xff]],
        png: [[0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]],
        gif: [[0x47, 0x49, 0x46, 0x38]], webp: [[0x52, 0x49, 0x46, 0x46]],
        bmp: [[0x42, 0x4d]], pdf: [[0x25, 0x50, 0x44, 0x46]],
    };
    var EXECUTABLES = [[0x4d, 0x5a], [0x7f, 0x45, 0x4c, 0x46], [0xca, 0xfe, 0xba, 0xbe],
                       [0xfe, 0xed, 0xfa, 0xce], [0xce, 0xfa, 0xed, 0xfe]];
    var EXECUTABLE_EXTS = ['exe', 'dll', 'so', 'bin', 'elf', 'dmg', 'app'];
    var instances = [];

    function extOf(name) {
        var i = name.lastIndexOf('.');
        return i > 0 ? name.slice(i + 1).toLowerCase() : '';
    }

    function formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / 1024 / 1024).toFixed(1) + ' MB';
    }

    function startsWith(bytes, sig) {
        if (bytes.length < sig.length) return false;
        for (var i = 0; i < sig.length; i++) if (bytes[i] !== sig[i]) return false;
        return true;
    }

    /* Resolves to null if the file's first bytes are plausible for its extension, else a reason. */
    function sniff(file, ext) {
        return file.slice(0, 16).arrayBuffer().then(function (buf) {
            var bytes = new Uint8Array(buf);
            if (EXECUTABLE_EXTS.indexOf(ext) < 0 && EXECUTABLES.some(function (s) { return startsWith(bytes, s); })) {
                return 'it is a program (executable) disguised as .' + ext;
            }
            if (SIGNATURES[ext] && !SIGNATURES[ext].some(function (s) { return startsWith(bytes, s); })) {
                return 'its content does not look like a .' + ext + ' file';
            }
            return null;
        }, function () { return 'it could not be read'; });
    }

    function fileIcon(thumb, ext) {
        thumb.replaceChildren(el('i', 'bi bi-file-earmark-text fs-3 text-muted'), el('span', 'pu-ext', ext.toUpperCase()));
    }

    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function PendingUploads(root) {
        this.root = root;
        this.rules = JSON.parse(root.dataset.rules || '{}');
        this.form = document.getElementById(root.dataset.form);
        this.existingSelector = root.dataset.existing || '';
        this.files = [];
        this.disabled = root.dataset.disabled === 'true';
        this.build();
        this.render();
    }

    PendingUploads.prototype.existingCount = function () {
        if (!this.existingSelector) return this.rules.existing || 0;
        return Array.prototype.filter.call(document.querySelectorAll(this.existingSelector), function (node) {
            return !node.classList.contains('pu-removing');
        }).length;
    };

    PendingUploads.prototype.remaining = function () {
        if (this.rules.maxFiles < 0) return Infinity;
        return Math.max(this.rules.maxFiles - this.existingCount() - this.files.length, 0);
    };

    PendingUploads.prototype.build = function () {
        var self = this, rules = this.rules;
        this.root.classList.add('pu-area');

        var bar = el('div', 'd-flex flex-wrap align-items-center gap-2');
        this.addButton = el('button', 'btn btn-sm btn-outline-primary');
        this.addButton.type = 'button';
        this.addButton.innerHTML = '<i class="bi bi-plus-lg"></i> Add files';
        this.hint = el('small', 'text-muted');
        bar.append(this.addButton, this.hint);

        this.picker = el('input');
        this.picker.type = 'file';
        this.picker.multiple = true;
        this.picker.hidden = true;
        if (rules.allowed && rules.allowed.length) {
            this.picker.accept = rules.allowed.map(function (e) { return '.' + e; }).join(',');
        }

        this.payload = el('input', 'pu-payload');
        this.payload.type = 'file';
        this.payload.multiple = true;
        this.payload.hidden = true;
        this.payload.name = this.root.dataset.name;
        if (this.form) this.payload.setAttribute('form', this.form.id);

        this.alerts = el('div', 'pu-alerts');
        this.list = el('div', 'pu-list d-flex flex-wrap gap-2');
        this.root.append(bar, this.alerts, this.list, this.picker, this.payload);

        if (this.disabled || rules.maxFiles === 0) {
            this.addButton.disabled = true;
        }
        this.addButton.addEventListener('click', function () { self.picker.click(); });
        this.picker.addEventListener('change', function () {
            self.add(Array.prototype.slice.call(self.picker.files));
            self.picker.value = '';
        });
        ['dragenter', 'dragover'].forEach(function (type) {
            self.root.addEventListener(type, function (e) {
                if (self.addButton.disabled || !e.dataTransfer || e.dataTransfer.types.indexOf('Files') < 0) return;
                e.preventDefault();
                self.root.classList.add('pu-dragover');
            });
        });
        ['dragleave', 'drop'].forEach(function (type) {
            self.root.addEventListener(type, function () { self.root.classList.remove('pu-dragover'); });
        });
        this.root.addEventListener('drop', function (e) {
            if (self.addButton.disabled || !e.dataTransfer || !e.dataTransfer.files.length) return;
            e.preventDefault();
            self.add(Array.prototype.slice.call(e.dataTransfer.files));
        });
    };

    PendingUploads.prototype.add = function (picked) {
        var self = this, rules = this.rules, problems = [];
        var checks = picked.map(function (file) {
            var ext = extOf(file.name);
            if (!ext) return Promise.resolve({ file: file, reason: 'it has no file extension' });
            if (rules.allowed.indexOf(ext) < 0) return Promise.resolve({ file: file, reason: '.' + ext + ' files are not permitted here' });
            if (file.size === 0) return Promise.resolve({ file: file, reason: 'it is empty' });
            if (file.size > rules.maxBytes) {
                return Promise.resolve({ file: file, reason: 'it is too large (' + formatSize(file.size) + '; the limit is ' + formatSize(rules.maxBytes) + ')' });
            }
            return sniff(file, ext).then(function (reason) { return { file: file, reason: reason }; });
        });
        Promise.all(checks).then(function (results) {
            results.forEach(function (r) {
                var duplicate = self.files.some(function (f) {
                    return f.name === r.file.name && f.size === r.file.size && f.lastModified === r.file.lastModified;
                });
                if (duplicate) return;
                if (!r.reason && self.remaining() < 1) {
                    r.reason = 'the limit of ' + rules.maxFiles + ' files is reached';
                }
                if (r.reason) problems.push('"' + r.file.name + '" was removed: ' + r.reason + '.');
                else self.files.push(r.file);
            });
            self.showProblems(problems);
            self.sync();
            self.render();
        });
    };

    PendingUploads.prototype.remove = function (index) {
        var file = this.files.splice(index, 1)[0];
        if (file && file._url) URL.revokeObjectURL(file._url);
        this.sync();
        this.render();
    };

    /* Put the accepted files into the hidden input that the form submits. */
    PendingUploads.prototype.sync = function () {
        var dt = new DataTransfer();
        this.files.forEach(function (f) { dt.items.add(f); });
        this.payload.files = dt.files;
    };

    PendingUploads.prototype.showProblems = function (problems) {
        this.alerts.replaceChildren();
        if (!problems.length) return;
        var box = el('div', 'alert alert-warning alert-dismissible py-2 px-3 mt-2 mb-0 small');
        var ul = el('ul', 'mb-0 ps-3');
        problems.forEach(function (p) { ul.appendChild(el('li', '', p)); });
        var close = el('button', 'btn-close');
        close.type = 'button';
        close.setAttribute('aria-label', 'Dismiss');
        close.style.padding = '.6rem';
        close.addEventListener('click', function () { box.remove(); });
        box.append(ul, close);
        this.alerts.appendChild(box);
    };

    PendingUploads.prototype.render = function () {
        var self = this, rules = this.rules;
        var parts = ['Allowed: ' + (rules.allowed.join(', ') || 'none'), 'max ' + formatSize(rules.maxBytes) + ' each'];
        if (rules.maxFiles === 0) parts = ['Uploads are turned off here'];
        else if (rules.maxFiles > 0) parts.push(this.existingCount() + this.files.length + ' of ' + rules.maxFiles + ' files');
        if (!this.disabled && rules.maxFiles !== 0) parts.push('or drop files here');
        this.hint.textContent = parts.join(' · ');
        this.addButton.disabled = this.disabled || rules.maxFiles === 0 || this.remaining() < 1;

        this.list.replaceChildren();
        this.list.classList.toggle('mt-2', this.files.length > 0);
        this.files.forEach(function (file, index) {
            var ext = extOf(file.name);
            var tile = el('div', 'pu-tile border rounded position-relative');
            tile.title = file.name + ' (' + formatSize(file.size) + ') — click to preview';
            tile.tabIndex = 0;
            var thumb = el('div', 'pu-thumb');
            if (IMAGE_EXTS.indexOf(ext) >= 0) {
                file._url = file._url || URL.createObjectURL(file);
                var img = el('img');
                img.src = file._url;
                img.alt = '';
                img.addEventListener('error', function () { fileIcon(thumb, ext); });
                thumb.appendChild(img);
            } else {
                fileIcon(thumb, ext);
            }
            var name = el('div', 'pu-name', file.name);
            var size = el('div', 'pu-size text-muted', formatSize(file.size));
            var badge = el('span', 'badge text-bg-info pu-new', 'New');
            var remove = el('button', 'btn btn-danger btn-sm pu-remove');
            remove.type = 'button';
            remove.innerHTML = '<i class="bi bi-x"></i>';
            remove.setAttribute('aria-label', 'Remove ' + file.name);
            remove.addEventListener('click', function (e) { e.stopPropagation(); self.remove(index); });
            tile.append(thumb, name, size, badge, remove);
            tile.addEventListener('click', function () { preview(file); });
            tile.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); preview(file); }
            });
            self.list.appendChild(tile);
        });
    };

    /* ── Preview ─────────────────────────────────────────────────────────── */
    var modal = null;
    function previewModal() {
        if (modal) return modal;
        var wrap = el('div', 'modal fade');
        wrap.tabIndex = -1;
        wrap.innerHTML =
            '<div class="modal-dialog modal-xl modal-dialog-centered modal-dialog-scrollable"><div class="modal-content">' +
            '<div class="modal-header"><h5 class="modal-title text-truncate"></h5>' +
            '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>' +
            '<div class="modal-body text-center"></div>' +
            '<div class="modal-footer"><small class="text-muted me-auto">Not uploaded yet — saved with the form.</small>' +
            '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button></div></div></div>';
        document.body.appendChild(wrap);
        modal = { el: wrap, bs: new bootstrap.Modal(wrap) };
        return modal;
    }

    function preview(file) {
        var m = previewModal(), ext = extOf(file.name);
        var body = m.el.querySelector('.modal-body');
        m.el.querySelector('.modal-title').textContent = file.name + ' · ' + formatSize(file.size);
        body.replaceChildren();
        file._url = file._url || URL.createObjectURL(file);
        if (IMAGE_EXTS.indexOf(ext) >= 0) {
            var img = el('img', 'img-fluid');
            img.src = file._url;
            img.alt = file.name;
            img.style.maxHeight = '75vh';
            body.appendChild(img);
        } else if (ext === 'pdf') {
            var frame = el('iframe');
            frame.src = file._url;
            frame.title = file.name;
            frame.style.cssText = 'width:100%;height:75vh;border:0;';
            body.appendChild(frame);
        } else if (TEXT_EXTS.indexOf(ext) >= 0) {
            var pre = el('pre', 'text-start small mb-0', 'Loading…');
            pre.style.cssText = 'max-height:75vh;white-space:pre-wrap;';
            body.appendChild(pre);
            file.slice(0, 200 * 1024).text().then(function (t) {
                pre.textContent = t + (file.size > 200 * 1024 ? '\n…' : '');
            });
        } else {
            body.appendChild(el('i', 'bi bi-file-earmark fs-1 text-muted d-block'));
            body.appendChild(el('p', 'text-muted mt-2 mb-0', 'No preview for .' + ext + ' files.'));
        }
        m.bs.show();
    }

    /* ── Wiring ──────────────────────────────────────────────────────────── */
    function mountAll() {
        document.querySelectorAll('.pending-uploads').forEach(function (root) {
            if (root._pendingUploads) return;
            root._pendingUploads = new PendingUploads(root);
            instances.push(root._pendingUploads);
            var form = root._pendingUploads.form;
            if (form && !form._pendingUploadsWired) {
                form._pendingUploadsWired = true;
                form.enctype = 'multipart/form-data';
                form.addEventListener('submit', function (e) {
                    var limit = parseInt(form.dataset.uploadLimit || '0', 10);
                    var total = instances.filter(function (i) { return i.form === form; })
                        .reduce(function (sum, i) { return sum + i.files.reduce(function (s, f) { return s + f.size; }, 0); }, 0);
                    if (limit && total > limit) {
                        e.preventDefault();
                        alert('The selected files add up to ' + formatSize(total) + ', more than the ' + formatSize(limit) +
                              ' that can be saved at once. Remove some files and save again.');
                    }
                });
            }
        });
    }

    document.addEventListener('pending-uploads:recount', function () {
        instances.forEach(function (i) { i.render(); });
    });
    document.addEventListener('DOMContentLoaded', mountAll);
    window.PendingUploads = { mountAll: mountAll };
})();

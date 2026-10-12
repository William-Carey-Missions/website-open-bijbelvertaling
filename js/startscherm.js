/* Startscherm van index.html — alleen als de pagina zonder #hash opent.
 *
 * Met een hash (#johannes/1, #psalmen/23/1 …) opent de lezer direct, zoals
 * altijd; alle bestaande deeplinks blijven dus werken. De keuze valt al in de
 * <head> (html.ov-start of html.ov-lezer), zodat er niets verspringt.
 *
 * Inhoud: Johannes 1:1–5 uit data/johannes/1.json, met het spoor (wijzigingen
 * t.o.v. SV1888), en de voortgang uit data/stats.json (data-stat, via
 * stats-inject.js; de balken vult dit script).
 */
(function (global) {
    'use strict';

    var root = document.documentElement;
    var LAATST = 'ov-laatst-gelezen';
    var oorspronkelijkeTitel = document.title;

    function isStart() { return root.classList.contains('ov-start'); }

    function toon() {
        root.classList.add('ov-start');
        root.classList.remove('ov-lezer');
        document.title = oorspronkelijkeTitel;
        global.scrollTo(0, 0);
        vulVerderLezen();
        return true;
    }

    function verberg() {
        if (!isStart()) return;
        root.classList.remove('ov-start');
        root.classList.add('ov-lezer');
        global.scrollTo(0, 0);
    }

    global.addEventListener('hashchange', function () {
        var hash = location.hash.slice(1);
        if (!hash) { toon(); return; }
        verberg();
        if (/^[a-z0-9]+\/\d+/i.test(hash)) {
            try { localStorage.setItem(LAATST, hash.split('/').slice(0, 2).join('/')); } catch (e) { /* privé-venster */ }
        }
    });
    if (!isStart() && /^#[a-z0-9]+\/\d+/i.test(location.hash)) {
        try { localStorage.setItem(LAATST, location.hash.slice(1).split('/').slice(0, 2).join('/')); } catch (e) { /* */ }
    }

    /* "Verder lezen: Psalmen 23" als er eerder gelezen is. */
    function vulVerderLezen() {
        var el = document.getElementById('ka-verder');
        if (!el) return;
        var laatst = null;
        try { laatst = localStorage.getItem(LAATST); } catch (e) { /* */ }
        if (!laatst || !/^[a-z0-9]+\/\d+$/i.test(laatst)) { el.textContent = ''; return; }
        var delen = laatst.split('/');
        var toonLink = function (naam) {
            el.textContent = 'Verder lezen: ';
            var a = document.createElement('a');
            a.href = '#' + laatst;
            a.textContent = naam + ' ' + delen[1];
            el.appendChild(a);
        };
        if (global.DataLoader && DataLoader.loadManifest) {
            DataLoader.loadManifest().then(function (m) {
                var boek = (m && m.books || []).find(function (b) { return b.id === delen[0]; });
                toonLink(boek ? (boek.nameDutch || boek.name || delen[0]) : delen[0]);
            }).catch(function () { toonLink(delen[0]); });
        } else {
            toonLink(delen[0]);
        }
    }

    /* Johannes 1:1–5 met het spoor */
    function vulPassage() {
        var doel = document.getElementById('ka-passage-tekst');
        var schakelaar = document.getElementById('ka-spoor-toggle');
        if (!doel) return;
        fetch('data/johannes/1.json')
            .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
            .then(function (hoofdstuk) {
                var verzen = (hoofdstuk.verses || []).filter(function (v) { return v.number >= 1 && v.number <= 5; });
                doel.textContent = '';
                verzen.forEach(function (vers, i) {
                    var html = vers.text2026_html || vers.text2026 || '';
                    html = html.replace(/<sup[^>]*>[\s\S]*?<\/sup>/g, '').replace(/\s{2,}/g, ' ').trim();
                    if (global.Opties && Opties.transformOV) {
                        try { html = Opties.transformOV(html, 'NT'); } catch (e) { /* tekst blijft onveranderd */ }
                    }
                    var nr = document.createElement('span');
                    nr.className = 'ka-vn';
                    nr.textContent = vers.number;
                    var tekst = document.createElement('span');
                    tekst.className = 'ka-vt';
                    tekst.innerHTML = html;
                    if (i) doel.appendChild(document.createTextNode(' '));
                    doel.appendChild(nr);
                    doel.appendChild(tekst);
                    if (global.OVSpoor) OVSpoor.markeer(tekst, vers, { altijd: true });
                });
                var sporen = doel.querySelectorAll('.spoor[tabindex]');
                var codes = {};
                sporen.forEach(function (s) { if (s.dataset.p && s.dataset.p !== 'los') codes[s.dataset.p] = 1; });
                var telling = document.getElementById('ka-passage-telling');
                var n = sporen.length, p = Object.keys(codes).length;
                if (telling) {
                    telling.textContent = n + (n === 1 ? ' wijziging' : ' wijzigingen') +
                        ' · ' + p + (p === 1 ? ' principe' : ' principes');
                }
                pasSpoorToe(schakelaar ? schakelaar.checked : true);
            })
            .catch(function () { /* de statische eerste zin blijft staan */ });

        if (schakelaar) {
            schakelaar.checked = global.OVSpoor ? OVSpoor.aan() : true;
            schakelaar.addEventListener('change', function () {
                var aan = schakelaar.checked;
                bewaarSpoor(aan);
                pasSpoorToe(aan);
            });
        }
    }

    function pasSpoorToe(aan) {
        var doel = document.getElementById('ka-passage-tekst');
        if (!doel) return;
        doel.classList.toggle('spoor-uit', !aan);
        doel.querySelectorAll('.spoor[data-sv]').forEach(function (s, i) {
            if (s.hasAttribute('aria-description')) s.tabIndex = aan ? 0 : -1;
        });
    }

    /* Dezelfde optie als in het optiepaneel ('spoor'), zodat de lezer volgt. */
    function bewaarSpoor(aan) {
        var waarde = aan ? 'aan' : 'uit';
        if (global.Opties && Opties._initialized) {
            Opties.state.spoor = waarde;
            Opties.save();
            var cb = document.getElementById('toggle-spoor');
            if (cb) cb.checked = aan;
            if (global.OptionsPanel && OptionsPanel.syncOptionMirrors) OptionsPanel.syncOptionMirrors();
            return;
        }
        try {
            var st = JSON.parse(localStorage.getItem('sv2026_vertaalopties') || '{}');
            st.spoor = waarde;
            localStorage.setItem('sv2026_vertaalopties', JSON.stringify(st));
        } catch (e) { /* */ }
    }

    function vulStatus() {
        var el = document.getElementById('ka-passage-status');
        if (!el || !global.App || !App._laadVerified) return;
        Promise.resolve(App._laadVerified()).then(function () {
            if (App._isVerified('johannes', 1)) {
                el.className = 'ka-pill ok';
                el.textContent = 'Gecontroleerd';
            }
        }).catch(function () { /* blijft 'Concept' */ });
    }

    function vulBalken() {
        fetch('data/stats.json')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (s) {
                if (!s) return;
                document.querySelectorAll('[data-stat-balk]').forEach(function (i) {
                    var v = Number(s[i.getAttribute('data-stat-balk')]);
                    if (isFinite(v)) i.style.width = Math.max(0, Math.min(100, v)) + '%';
                });
            })
            .catch(function () { /* */ });
    }

    // Spoor ook in het optiepaneel omgezet? Dan volgt de passage.
    global.addEventListener('ov:opties-gewijzigd', function (e) {
        var st = e.detail && e.detail.state;
        if (!st) return;
        var aan = st.spoor !== 'uit';
        var cb = document.getElementById('ka-spoor-toggle');
        if (cb) cb.checked = aan;
        pasSpoorToe(aan);
    });

    function init() {
        vulVerderLezen();
        vulPassage();
        vulStatus();
        vulBalken();
    }

    global.OVStart = { toon: toon, verberg: verberg, isStart: isStart };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})(window);

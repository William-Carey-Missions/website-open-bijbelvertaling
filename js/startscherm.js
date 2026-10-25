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
                if (boek) toonLink(boek.nameDutch || boek.name || delen[0]);
            }).catch(function () { toonLink(delen[0]); });
        } else {
            toonLink(delen[0]);
        }
    }

    /* Johannes 1:1–5 met het spoor */
    function vulPassage() {
        var doel = document.getElementById('ka-passage-tekst');
        var schakelaar = null;
        if (!doel) return;
        fetch('data/johannes/1.json')
            .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
            .then(function (hoofdstuk) {
                var verzen = (hoofdstuk.verses || []).filter(function (v) { return v.number >= 1 && v.number <= 5; });
                doel.textContent = '';
                verzen.forEach(function (vers, i) {
                    // De nootcijfers blijven staan: ze verwijzen naar de kanttekeningen ernaast.
                    var html = (vers.text2026_html || vers.text2026 || '').replace(/\s{2,}/g, ' ').trim();
                    if (global.Opties && Opties.transformOV) {
                        try { html = Opties.transformOV(html, 'NT'); } catch (e) { /* tekst blijft onveranderd */ }
                    }
                    var nr = document.createElement('span');
                    nr.className = 'ka-vn';
                    nr.textContent = vers.number;
                    var tekst = document.createElement('a');
                    tekst.className = 'ka-vt';
                    tekst.href = '#johannes/1/' + vers.number;
                    tekst.title = 'Lees Johannes 1:' + vers.number;
                    tekst.innerHTML = html;
                    if (i) doel.appendChild(document.createTextNode(' '));
                    doel.appendChild(nr);
                    doel.appendChild(tekst);
                });
                vulKanttekeningen(verzen, doel);
                var sporen = doel.querySelectorAll('.spoor[tabindex]');
                var codes = {};
                sporen.forEach(function (s) { if (s.dataset.p && s.dataset.p !== 'los') codes[s.dataset.p] = 1; });
                var telling = document.getElementById('ka-passage-telling');
                var n = sporen.length, p = Object.keys(codes).length;
                if (telling) {
                    telling.textContent = n + (n === 1 ? ' wijziging' : ' wijzigingen') +
                        ' · ' + p + (p === 1 ? ' principe' : ' principes');
                }

            })
            .catch(function () { /* de statische eerste zin blijft staan */ });


    }

    /* De kanttekeningen bij Johannes 1:1–5, naast de tekst. Een klik op een
       nootcijfer in de tekst licht de bijbehorende noot op. */
    function vulKanttekeningen(verzen, tekst) {
        var lijst = document.getElementById('ka-passage-kt');
        if (!lijst) return;
        lijst.textContent = '';
        verzen.forEach(function (vers) {
            (vers.marginNotes || []).forEach(function (noot) {
                var bron = noot.text2026 || noot.text1637;
                if (!bron) return;
                var item = document.createElement('p');
                item.className = 'kt-item' + (noot.type === 'crossref' ? ' kt-verwijzing' : '');
                item.dataset.note = noot.marker;
                var merk = document.createElement('b');
                merk.className = 'kt-m';
                merk.textContent = noot.marker;
                var inhoud = document.createElement('span');
                if (typeof References !== 'undefined' && References.linkify) inhoud.innerHTML = References.linkify(bron, 'johannes', 1);
                else inhoud.textContent = bron;
                linkGriekseWoorden(inhoud, vers);
                item.appendChild(merk);
                item.appendChild(document.createTextNode(' '));
                item.appendChild(inhoud);
                lijst.appendChild(item);
            });
        });
        tekst.addEventListener('click', function (e) {
            var merk = e.target.closest && e.target.closest('.note-marker');
            if (!merk) return;
            e.preventDefault();
            var doelNoot = Array.prototype.find.call(lijst.querySelectorAll('.kt-item'),
                function (item) { return item.dataset.note === merk.dataset.note; });
            if (!doelNoot) return;
            lijst.querySelectorAll('.kt-item.is-actief').forEach(function (item) { item.classList.remove('is-actief'); });
            doelNoot.classList.add('is-actief');
            lijst.scrollTo({ top: doelNoot.offsetTop - lijst.offsetTop - 8, behavior: 'smooth' });
        });
    }

    function linkGriekseWoorden(container, vers) {
        var normaliseer = function (word) { return word.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/ς/g, 'σ'); };
        var woorden = new Map();
        (vers.grondtekst || []).forEach(function (word) {
            var number = String(word.strongs || '').match(/^G\d+/);
            if (number) woorden.set(normaliseer(word.woord || ''), number[0]);
        });
        var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, {
            acceptNode: function (text) { return text.parentElement.closest('a,button') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT; }
        });
        var nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);
        nodes.forEach(function (text) {
            var pattern = /[\u0370-\u03ff\u1f00-\u1fff]+/g;
            var fragment = document.createDocumentFragment(), offset = 0, found = false;
            for (var match of text.textContent.matchAll(pattern)) {
                var number = woorden.get(normaliseer(match[0]));
                if (!number) continue;
                found = true;
                fragment.appendChild(document.createTextNode(text.textContent.slice(offset, match.index)));
                var link = document.createElement('a');
                link.className = 'ka-greek-link';
                link.href = 'https://opengodsword.com/lexicon-viewer.html?taal=grieks&entry=' + encodeURIComponent(number);
                link.title = 'Lees de betekenis van ' + match[0] + ' bij Open Gods Word';
                link.lang = 'grc'; link.textContent = match[0];
                fragment.appendChild(link); offset = match.index + match[0].length;
            }
            if (found) { fragment.appendChild(document.createTextNode(text.textContent.slice(offset))); text.replaceWith(fragment); }
        });
    }

    function vulStatus() {
        var el = document.getElementById('ka-passage-status');
        if (!el || !global.App || !App._laadVerified) return;
        Promise.resolve(App._laadVerified()).then(function () {
            if (App._isVerified('johannes', 1)) {
                el.className = 'ka-pill ok';
                el.textContent = 'Gecontroleerd';
            }
        }).catch(function () { /* De publicatietekst blijft staan. */ });
    }

    function init() {
        vulVerderLezen();
        vulPassage();
        vulStatus();

    }

    global.OVStart = { toon: toon, verberg: verberg, isStart: isStart };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})(window);

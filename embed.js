/* ============================================================================
 * OSV Citaat-bibliotheek  (embed.js)
 * Embed citaten uit de Open Vertaling op deze én op andere websites.
 *
 * ÉÉN BRON: de tekst wordt live van openvertaling.nl geladen — er wordt geen
 * kopie gemaakt. Wijzigt de OSV, dan wijzigt het citaat overal mee. De bron
 * verwijst altijd terug naar openvertaling.nl.
 *
 * Gebruik (HTML, auto):
 *   <script src="https://openvertaling.nl/embed.js" defer></script>
 *   <span data-osv="johannes 3:16"></span>
 *   <div  data-osv="psalmen 23:1-4" data-osv-godsnaam="klassiek" data-osv-numbers="true"></div>
 *
 * Opties (als data-osv-… attributen of in OSV.cite(ref, opts)):
 *   numbers   true|false   versnummers tonen          (standaard true)
 *   citaat    true|false   citaatopmaak (rood=God enz.)(standaard true)
 *   link      true|false   bronverwijzing tonen        (standaard true)
 *   godsnaam  ov|klassiek|jehovah|yehovah|jhwh|yhwh    (standaard ov = JAHWEH)
 *   strongs   true|false   bronvaste woordnummers tonen (standaard: globale voorkeur)
 *
 * Via JavaScript:
 *   OSV.cite('johannes 3:16', {numbers:false}).then(r => el.innerHTML = r.html);
 * ========================================================================== */
(function (global) {
  'use strict';

  var SITE = 'https://openvertaling.nl';
  var script = document.currentScript;

  function inferBase() {
    if (script && script.dataset && script.dataset.base) return script.dataset.base.replace(/\/$/, '');
    if (global.OSV_BASE) return String(global.OSV_BASE).replace(/\/$/, '');
    try {
      var h = location.hostname;
      if (h === 'openvertaling.nl' || h.endsWith('.openvertaling.nl') ||
          h === 'localhost' || h === '127.0.0.1') return '';
    } catch (e) {}
    return SITE; // extern: laad van productie
  }
  var BASE = inferBase();

  var chapterCache = {};
  var wordMappingCache = {};
  var booksPromise = null;
  var wordNumberPromise = null;
  var editionsPromise = null;
  var editionChapterCache = {};

  function mergeInlineMappings(chapter, mappingBook, chapterNumber) {
    if (!chapter || !mappingBook || !mappingBook.chapters) return chapter;
    var external = mappingBook.chapters[String(chapterNumber)] || {};
    (chapter.verses || []).forEach(function (verse) {
      var generated = external[String(verse.number)] || [];
      if (!generated.length) return;
      var merged = {};
      generated.concat(verse.woordnummers || []).forEach(function (mapping) {
        var key = String(mapping.tekst || '').toLocaleLowerCase('nl') + '#' + (mapping.voorkomen || 1);
        merged[key] = mapping;
      });
      verse.woordnummers = Object.keys(merged).map(function (key) { return merged[key]; });
    });
    return chapter;
  }

  function storedStrongPreference() {
    try {
      var saved = JSON.parse(localStorage.getItem('sv2026_vertaalopties') || '{}');
      return saved.strongs === 'aan';
    } catch (e) { return false; }
  }

  function ensureWordNumberSupport(enabled) {
    if (!enabled) return Promise.resolve();
    if (!wordNumberPromise) {
      var rendererReady = global.OVWoordnummers ? Promise.resolve() : new Promise(function (resolve) {
          var tag = document.createElement('script');
          tag.src = BASE + '/js/woordnummers.js';
          tag.onload = resolve;
          tag.onerror = resolve;
          document.head.appendChild(tag);
        });
      wordNumberPromise = rendererReady.then(function () {
        if (global.Lexicon) return;
        return new Promise(function (resolve) {
          var tag = document.createElement('script');
          tag.src = BASE + '/js/lexicon.js';
          tag.onload = resolve;
          tag.onerror = resolve;
          document.head.appendChild(tag);
        });
      }).then(function () {
        if (global.Lexicon) global.Lexicon.init();
      });
    }
    return wordNumberPromise;
  }

  /* Lichte citaatbestanden, gebouwd door scripts/build_citaten.py. Een
     bewijstekst heeft van een hoofdstuk alleen het versnummer en de tekst
     nodig; het volledige hoofdstukbestand weegt dertig keer zoveel. Het zijn
     scripts en geen JSON, omdat een <script> ook vanaf een andere site geladen
     mag worden: zo komt de tekst op Open Gods Woord en op externe sites
     rechtstreeks van openvertaling.nl, zonder dat de server daarvoor CORS hoeft
     toe te staan. Elk bestand roept OSV._ontvang aan met zijn eigen sleutel.
     Ontbreekt een bestand — lokaal zonder bouwstap — dan valt het laden terug
     op de JSON van het hoofdstuk. */
  var citaatWachtend = {};
  var citaatCache = {};

  function ontvang(sleutel, data) {
    var klaar = citaatWachtend[sleutel];
    if (!klaar) return;
    delete citaatWachtend[sleutel];
    klaar(data);
  }

  function laadCitaat(sleutel, pad) {
    if (!citaatCache[sleutel]) {
      citaatCache[sleutel] = new Promise(function (resolve, reject) {
        var tag = document.createElement('script');
        // Zonder echte DOM — een testomgeving, een worker — laadt een <script>
        // nooit en zou het citaat eeuwig wachten; dan meteen naar de JSON.
        if (!document.head || typeof tag.setAttribute !== 'function') {
          reject(new Error('Geen DOM om citaatbestanden te laden'));
          return;
        }
        citaatWachtend[sleutel] = resolve;
        tag.src = BASE + '/data/citaat/' + pad;
        tag.async = true;
        function afgerond(fout) {
          if (tag.parentNode) tag.parentNode.removeChild(tag);
          // Een bestand dat er niet is, beantwoordt de server met een
          // HTML-pagina: die laadt wel, maar roept OSV._ontvang nooit aan.
          if (!citaatWachtend[sleutel]) return;
          delete citaatWachtend[sleutel];
          reject(fout || new Error('Geen citaatdata in ' + pad));
        }
        tag.onload = function () { afgerond(); };
        tag.onerror = function () { afgerond(new Error(pad + ' niet geladen')); };
        document.head.appendChild(tag);
      });
    }
    return citaatCache[sleutel];
  }

  function loadBooks() {
    if (!booksPromise) {
      booksPromise = laadCitaat('boeken', 'boeken.js')
        .then(function (d) {
          var m = {};
          Object.keys(d).forEach(function (id) {
            m[id] = { id: id, nameDutch: d[id].naam, testament: d[id].testament };
          });
          return m;
        })
        .catch(function () {
          return fetch(BASE + '/data/books.json')
            .then(function (r) { return r.json(); })
            .then(function (d) {
              var m = {};
              (d.books || []).forEach(function (b) { m[b.id] = b; });
              return m;
            });
        })
        .catch(function () { return {}; });
    }
    return booksPromise;
  }

  /* De woordnummers zijn zwaar en alleen nodig als Strong aan staat; ze staan
     daarom in een eigen bestand, dat er alleen is als het hoofdstuk ze heeft. */
  function loadChapter(book, ch, metWoorden) {
    var sleutel = book + '/' + ch;
    return laadCitaat(sleutel, sleutel + '.js').then(function (citaat) {
      // Elke aanroep krijgt eigen versobjecten, zodat de woordnummers van de
      // ene aanroep niet in de gedeelde cache van de andere belanden.
      var chapter = {
        verses: citaat.verzen.map(function (regel) {
          return { number: regel[0], text2026_html: regel[1], text2026: regel[2] };
        })
      };
      if (!metWoorden || !citaat.woorden) return chapter;
      return laadCitaat(sleutel + '#woorden', sleutel + '.woorden.js').then(function (woorden) {
        chapter.verses.forEach(function (v) { v.woordnummers = woorden[String(v.number)] || []; });
        return chapter;
      }, function () { return chapter; });
    }, function () {
      return loadChapterJson(book, ch);
    });
  }

  function loadChapterJson(book, ch) {
    var key = book + '/' + ch;
    if (!chapterCache[key]) {
      var chapterRequest = fetch(BASE + '/data/' + book + '/' + ch + '.json')
        .then(function (r) { if (!r.ok) throw new Error('niet gevonden'); return r.json(); });
      if (!wordMappingCache[book]) {
        wordMappingCache[book] = fetch(BASE + '/data/woordnummers-inline/' + book + '.json')
          .then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
      }
      chapterCache[key] = Promise.all([chapterRequest, wordMappingCache[book]]).then(function (items) {
        var chapter = items[0], mappings = items[1];
        return mergeInlineMappings(chapter, mappings, ch);
      });
    }
    return chapterCache[key];
  }

  function loadEditions() {
    if (!editionsPromise) {
      editionsPromise = fetch(BASE + '/data/vertalingen/manifest.json')
        .then(function (r) { if (!r.ok) throw new Error('vertalingenmanifest niet gevonden'); return r.json(); })
        .then(function (data) { return data.edities || []; });
    }
    return editionsPromise;
  }

  function selectedEdition(opts) {
    var requested = opts.edition || opts.editie;
    if (requested) return requested;
    if (global.TekstEditie && typeof global.TekstEditie.code === 'function') return global.TekstEditie.code();
    try {
      return JSON.parse(localStorage.getItem('sv2026_vertaalopties') || '{}').teksteditie || 'nl-ov';
    } catch (e) {
      return 'nl-ov';
    }
  }

  function loadEditionChapter(edition, book, ch, metWoorden) {
    if (edition === 'nl-ov') return loadChapter(book, ch, metWoorden);
    var key = edition + ':' + book + '/' + ch;
    if (!editionChapterCache[key]) {
      editionChapterCache[key] = fetch(BASE + '/data/vertalingen/' + edition + '/' + book + '/' + ch + '.json')
        .then(function (r) { if (!r.ok) throw new Error('vertaling niet gevonden'); return r.json(); });
    }
    return editionChapterCache[key];
  }

  function parseRef(ref) {
    var m = String(ref || '').trim().match(/^(\S+)\s+(\d+):(\d+)(?:\s*-\s*(\d+))?$/);
    if (!m) return null;
    return { book: m[1].toLowerCase(), chapter: +m[2], from: +m[3], to: +(m[4] || m[3]) };
  }

  /* Godsnaam-transform (zoals js/opties.js), alleen buiten HTML-tags */
  function replaceOutsideTags(html, pairs) {
    var re = /(<[^>]+>)|([^<]+)/g, out = '', m;
    while ((m = re.exec(html)) !== null) {
      if (m[1]) { out += m[1]; }
      else {
        var txt = m[2];
        for (var i = 0; i < pairs.length; i++) txt = txt.replace(pairs[i][0], pairs[i][1]);
        out += txt;
      }
    }
    return out;
  }
  function applyGodsnaam(html, mode) {
    if (mode === 'klassiek') {
      return replaceOutsideTags(html, [
        [/\bGod JAHWEH\b/g, 'de HEERE God'],
        [/\bJAHWEH van de legermachten\b/g, 'de HEERE der heirscharen'],
        [/\b(op|van|aan|voor|tot|door|in|met|bij|over|onder|naast|achter|jegens|uit|na|sinds) JAHWEH\b/gi, '$1 de HEERE'],
        [/\b([Oo]) JAHWEH\b/g, '$1 HEERE'],
        [/\bJAHWEH!/g, 'HEERE!'],
        [/(^|[.!?]\s+)JAHWEH\b/g, '$1De HEERE'],
        [/\bJAHWEH\b/g, 'de HEERE'],
        [/\bde de HEERE\b/g, 'de HEERE'],
        [/\bDe de HEERE\b/g, 'De HEERE'],
      ]);
    } else if (mode === 'jehovah') {
      return replaceOutsideTags(html, [[/\bGod JAHWEH\b/g, 'God Jehovah'], [/\bJAHWEH\b/g, 'Jehovah']]);
    } else if (mode === 'yehovah') {
      return replaceOutsideTags(html, [[/\bGod JAHWEH\b/g, 'God Yehováh'], [/\bJAHWEH\b/g, 'Yehováh']]);
    } else if (mode === 'jhwh') {
      return replaceOutsideTags(html, [[/\bGod JAHWEH\b/g, 'God יהוה'], [/\bJAHWEH\b/g, 'יהוה']]);
    } else if (mode === 'yhwh') {
      return replaceOutsideTags(html, [[/\bGod JAHWEH\b/g, 'God YHWH'], [/\bJAHWEH\b/g, 'YHWH']]);
    }
    return html;
  }

  function bool(v, def) {
    if (v === undefined || v === null || v === '') return def;
    if (typeof v === 'boolean') return v;
    return !/^(false|0|nee|no|uit)$/i.test(String(v));
  }

  /* Hoofd-API: levert {html, plain, ref, label, url} voor een referentie */
  function cite(ref, opts) {
    opts = opts || {};
    var globalOptions = typeof Opties !== 'undefined' && Opties.state;
    var sharedView = global.OVTekstweergave;
    var numbersDefault = globalOptions ? globalOptions.versnummers !== 'uit' : true;
    var numbers = sharedView
      ? sharedView.versnummersAan(opts)
      : bool(opts.numbers, numbersDefault);
    var citaat = sharedView
      ? sharedView.citatenAan(opts)
      : bool(opts.citaat, true);
    var showLink = bool(opts.link, true);
    var gods = opts.godsnaam || 'ov';
    var showWordNumbers = bool(
      opts.strongs,
      globalOptions ? globalOptions.strongs === 'aan' : storedStrongPreference()
    );

    var p = parseRef(ref);
    if (!p) return Promise.reject(new Error('Ongeldige referentie: ' + ref));
    var edition = selectedEdition(opts);

    var optionsReady = typeof Opties !== 'undefined' && Opties.ready
      ? Opties.ready : Promise.resolve();
    return Promise.all([
      loadEditionChapter(edition, p.book, p.chapter, showWordNumbers),
      loadBooks(), optionsReady, ensureWordNumberSupport(showWordNumbers),
      edition === 'nl-ov' ? Promise.resolve(null) : loadEditions()
    ]).then(function (res) {
      var data = res[0], books = res[1], book = books[p.book] || {};
      var editionMeta = edition === 'nl-ov'
        ? { code: 'nl-ov', taal: 'nl', richting: 'ltr', naam: 'Open Vertaling' }
        : (res[4] || []).filter(function (item) { return item.code === edition; })[0];
      if (!editionMeta) throw new Error('Onbekende teksteditie: ' + edition);
      var external = edition !== 'nl-ov';
      var name = book.nameDutch || p.book;
      var verses = data.verses || data.verzen || [];
      var picked = verses.filter(function (v) {
        var number = v.number || v.nummer;
        return number >= p.from && number <= p.to;
      });
      if (!picked.length) throw new Error('Vers niet gevonden: ' + ref);

      var parts = picked.map(function (v) {
        var number = v.number || v.nummer;
        var html = v.text2026_html || v.html || v.text2026 || v.tekst || '';
        var text = v.text2026 || v.tekst || '';
        var body = citaat ? html : text;
        if (!citaat) body = escapeHtml(body);
        if (!external && sharedView && opts.godsnaam === undefined) {
          body = sharedView.transformeer(body, {
            boek: p.book, hoofdstuk: p.chapter, vers: number, testament: book.testament
          }, opts);
        } else if (!external && typeof Opties !== 'undefined' && Opties.transformOV && opts.godsnaam === undefined) {
          body = Opties.transformOV(body, book.testament);
          if (Opties.markeerGeo) body = Opties.markeerGeo(body, p.book, p.chapter, number);
          if (Opties.rekenMaten) body = Opties.rekenMaten(body, p.book, p.chapter, number);
          if (Opties.rekenTijden) body = Opties.rekenTijden(body, p.book, p.chapter, number, book.testament);
        } else if (!external) {
          body = applyGodsnaam(body, gods);
        }
        var num = numbers ? '<sup class="osv-num">' + number + '</sup> ' : '';
        if (!external && showWordNumbers && global.OVWoordnummers) {
          body = global.OVWoordnummers.renderInline(body, v.woordnummers || []);
        }
        return '<span class="osv-vers">' + num + body + '</span>';
      });

      var label = name + ' ' + p.chapter + ':' + p.from + (p.to !== p.from ? '-' + p.to : '');
      var url = SITE + '/index.html' + (external ? '?editie=' + encodeURIComponent(edition) : '') + '#' + p.book + '/' + p.chapter;
      var linkHtml = showLink
        ? '<a class="osv-bron" href="' + url + '" target="_blank" rel="noopener">— ' + label +
          ' <span class="osv-merk">(Open Vertaling)</span></a>'
        : '';
      var html = '<span class="osv-tekst" translate="no" lang="' + escapeHtml(editionMeta.taal || 'nl') + '"' +
        ((editionMeta.richting || 'ltr') === 'rtl' ? ' dir="rtl"' : '') + '>' + parts.join(' ') + '</span>' + linkHtml;

      var plain = picked.map(function (v) {
        var number = v.number || v.nummer;
        var t = v.text2026 || v.tekst || '';
        if (!external && sharedView && opts.godsnaam === undefined) {
          t = sharedView.transformeer(t, {
            boek: p.book, hoofdstuk: p.chapter, vers: number, testament: book.testament
          }, opts);
        } else if (!external && typeof Opties !== 'undefined' && Opties.transformOV && opts.godsnaam === undefined) {
          t = Opties.transformOV(t, book.testament);
          if (Opties.rekenMaten) t = Opties.rekenMaten(t, p.book, p.chapter, number);
          if (Opties.rekenTijden) t = Opties.rekenTijden(t, p.book, p.chapter, number, book.testament);
        } else if (!external) {
          t = applyGodsnaam(t, gods);
        }
        return (numbers ? number + ' ' : '') + t;
      }).join(' ');

      return { html: html, plain: plain, ref: ref, label: label, url: url, editie: edition, taal: editionMeta.taal, richting: editionMeta.richting };
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]; });
  }

  function renderEl(el, force) {
    if (!force && el.getAttribute('data-osv-done') === '1') return;
    el.setAttribute('data-osv-done', '1');
    var ref = el.getAttribute('data-osv');
    var opts = {
      numbers: el.getAttribute('data-osv-numbers'),
      citaat: el.getAttribute('data-osv-citaat'),
      link: el.getAttribute('data-osv-link'),
      godsnaam: el.getAttribute('data-osv-godsnaam') || undefined,
      edition: el.getAttribute('data-osv-edition') || undefined
      ,strongs: el.getAttribute('data-osv-strongs')
    };
    el.classList.add('osv-cite');
    el.innerHTML = '<span class="osv-laden">…</span>';
    cite(ref, opts).then(function (r) {
      el.innerHTML = r.html;
      if (r.taal) el.setAttribute('lang', r.taal);
      if (r.richting === 'rtl') el.setAttribute('dir', 'rtl');
      else el.removeAttribute('dir');
      if (r.editie) el.setAttribute('data-osv-editie', r.editie);
    })
      .catch(function (e) { el.innerHTML = '<span class="osv-fout">[' + (ref || '') + ' niet gevonden]</span>'; });
  }

  function renderAll(root, force) {
    var selector = force ? '[data-osv]' : '[data-osv]:not([data-osv-done="1"])';
    (root || document).querySelectorAll(selector).forEach(function (el) { renderEl(el, force); });
  }

  /* Scoped CSS injecteren (werkt ook op externe sites) */
  function injectCss() {
    if (document.getElementById('osv-embed-css')) return;
    var css =
      '.osv-cite{font-family:Georgia,"Times New Roman",serif;line-height:1.6;color:inherit;}' +
      '.osv-cite .osv-num{font-size:.7em;font-weight:700;color:#cba449;vertical-align:super;margin-right:1px;}' +
      '.osv-cite .osv-vers{}' +
      '.osv-cite .god-speaks{color:#c0392b;font-style:italic;}' +
      '.osv-cite .direct-speech{font-style:italic;}' +
      '.osv-cite .direct-speech::before{content:"“";}.osv-cite .direct-speech::after{content:"”";}' +
      '.osv-cite .devil-speaks{color:#b8860b;font-style:italic;}' +
      '.osv-cite .angel-speaks{color:#1d4ed8;font-style:italic;}' +
      '.osv-cite .note-marker{display:none;}' +
      '.osv-cite .strongs-alignment{display:flex;flex-wrap:wrap;gap:5px 9px;margin-top:.55em;padding-top:.45em;border-top:1px solid rgba(120,100,70,.18);direction:rtl;user-select:none;}' +
      '.osv-cite .strongs-alignment-ltr{direction:ltr;}.osv-cite .strongs-token{display:inline-flex;flex-direction:column;align-items:center;direction:ltr;}' +
      '.osv-cite .strongs-source-word{font-size:.92em;line-height:1.1;}.osv-cite .strongs-inline{display:inline-block;border:0;background:transparent;color:#246da8;font:inherit;font-size:.58em;cursor:pointer;}' +
      '.osv-cite .osv-bron{display:block;margin-top:.4em;font-family:system-ui,sans-serif;font-size:.8em;color:#7a6a3a;text-decoration:none;}' +
      '.osv-cite .osv-bron:hover{text-decoration:underline;}' +
      '.osv-cite .osv-merk{opacity:.75;}' +
      '.osv-cite .osv-laden{opacity:.5;}' +
      '.osv-cite .osv-fout{color:#999;font-style:italic;font-size:.9em;}' +
      '@media (prefers-color-scheme:dark){.osv-cite .god-speaks{color:#ff7a6c;}.osv-cite .angel-speaks{color:#7ab0ff;}.osv-cite .osv-bron{color:#cba449;}}';
    var s = document.createElement('style');
    s.id = 'osv-embed-css';
    s.textContent = css;
    document.head.appendChild(s);
  }

  var OSV = {
    cite: cite,
    render: renderEl,
    renderAll: renderAll,
    refresh: function (root) { renderAll(root, true); },
    base: BASE,
    site: SITE,
    _loadChapter: loadChapter,
    _ontvang: ontvang
  };
  global.OSV = OSV;

  injectCss();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { renderAll(); });
  } else {
    renderAll();
  }
})(typeof window !== 'undefined' ? window : this);

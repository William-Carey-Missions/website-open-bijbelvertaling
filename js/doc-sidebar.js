/* Gedeelde documentatienavigatie; pagina's kiezen alleen hun menuvariant. */
(function () {
    const links = {
        uitgangspunten: 'Uitgangspunten & techniek',
        principes: 'Wijzigingsprincipes',
        statistieken: 'Statistieken',
        maateenheden: 'Maateenheden',
        grondteksten: 'Grondteksten',
        geografie: 'Geografische aanduidingen',
        'handschriften-henoch': '↳ Handschriften Henoch',
        handschriften: '↳ Alle handschriften',
        changelog: 'Changelog',
        'lexicon-bdb': 'Hebreeuws (BDB)',
        'lexicon-abbott': 'Grieks (Abbott-Smith)',
    };
    // Achtergrondpagina's staan op Open Gods Woord (zie js/sites.js).
    const opOGW = new Set(['maateenheden', 'geografie', 'handschriften-henoch', 'handschriften', 'lexicon-bdb', 'lexicon-abbott']);
    const main = ['uitgangspunten', 'principes', 'statistieken', 'maateenheden', 'grondteksten'];
    const lexicons = ['lexicon-bdb', 'lexicon-abbott'];
    const menus = {
        geografie: ['uitgangspunten', 'principes', 'maateenheden', 'grondteksten', 'geografie', 'changelog'],
        grondteksten: [...main, 'handschriften-henoch', 'changelog', ...lexicons],
        henoch: [...main, 'handschriften-henoch', 'changelog'],
        handschriften: [...main, 'handschriften', 'changelog'],
        lexicon: [...main, 'changelog', ...lexicons],
    };
    const nav = document.querySelector('.doc-sidebar');
    const page = location.pathname.split('/').pop();
    nav.setAttribute('aria-label', 'Documentatie');

    function heading(text, className) {
        const title = document.createElement('div');
        title.className = className;
        title.textContent = text;
        nav.appendChild(title);
    }

    heading('Documentatie', 'doc-sidebar-title');
    for (const id of menus[nav.dataset.docMenu]) {
        if (id === lexicons[0]) heading('Lexicons', 'doc-sidebar-section');
        const link = document.createElement('a');
        link.href = id + '.html';
        link.textContent = links[id];
        if (opOGW.has(id)) {
            link.href = 'https://opengodsword.com/' + id + '.html';
            link.setAttribute('data-ogw-href', id + '.html');
            link.textContent += ' ↗';
        }
        if (id === 'handschriften' || id === 'handschriften-henoch') link.className = 'doc-sidebar-child';
        if (page === id + '.html') link.setAttribute('aria-current', 'page');
        nav.appendChild(link);
    }
    if (window.KASites) window.KASites.vulLinks(nav);
})();

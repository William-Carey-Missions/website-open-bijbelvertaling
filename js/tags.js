/* Tags — Topicale tags op bijbelverzen */

const Tags = {
    data: null,
    loaded: false,
    verseLookup: {},  // "genesis 1:3" -> [{tag object}]
    naslag: null,     // vers -> naslagingangen (dieren, planten, materialen, instrumenten)

    async ensureLoaded() {
        if (this.loaded) return;
        try {
            const resp = await fetch('data/tags.json');
            this.data = await resp.json();
            this.buildLookup();
            this.loaded = true;
        } catch (e) {
            console.warn('Tags laden mislukt:', e);
            this.data = { tags: [] };
            this.loaded = true;
        }
        // De optie "Tekstverbanden" belooft ook dieren, planten, materialen en
        // muziekinstrumenten. Die staan niet in tags.json maar in de
        // naslagverzamelingen; scripts/build_naslag_verzen.py maakt daar een
        // compacte vers-index van, want de verzamelingen zelf zijn samen ruim
        // twee megabyte. Mislukt het laden, dan blijven de thematische tags
        // gewoon werken.
        if (this.naslag === null) {
            try {
                const r = await fetch('data/naslag-verzen.json');
                this.naslag = await r.json();
            } catch (e) {
                console.warn('Naslagverwijzingen laden mislukt:', e);
                this.naslag = { categorieen: {}, namen: {}, verzen: {} };
            }
        }
    },

    /* De naslagingangen bij één vers, in dezelfde vorm als een thematische tag,
       zodat renderTagsForChapter ze niet apart hoeft te behandelen. */
    naslagVoor(ref) {
        if (!this.naslag || !this.naslag.verzen) return [];
        const paren = this.naslag.verzen[ref];
        if (!paren) return [];
        return paren.map(([categorie, id]) => {
            const cat = this.naslag.categorieen[categorie] || {};
            const naam = this.naslag.namen[categorie + '/' + id] || id;
            return {
                naam: naam,
                kleur: cat.kleur || '#999',
                // De naslagpagina kiest zijn ingang uit ?item=, niet uit de hash
                // De naslag staat op Open Gods Woord, niet op de OV-site zelf.
                naslagUrl: KASites.url('ogw', (cat.pagina || '') + '?item=' + encodeURIComponent(id)),
                categorieLabel: cat.label || categorie
            };
        });
    },

    buildLookup() {
        this.verseLookup = {};
        for (const tag of this.data.tags) {
            for (const item of tag.verzen) {
                const ref = typeof item === 'string' ? item : item.ref;
                if (!this.verseLookup[ref]) this.verseLookup[ref] = [];
                this.verseLookup[ref].push(tag);
            }
        }
    },

    // Toon tags bij een vers (kleine labels onder het versnummer)
    async renderTagsForChapter(bookId, chapterNum) {
        // Zonder de optie Tekstverbanden zijn de labels onzichtbaar; dan hoeven
        // tags.json en naslag-verzen.json (samen ruim twee megabyte) niet mee te
        // komen. Gaat de optie aan, dan tekent de lezer het hoofdstuk opnieuw.
        if (!document.body.classList.contains('show-tags')) return;
        await this.ensureLoaded();
        const rows = document.querySelectorAll('.verse-row');
        rows.forEach(row => {
            const vNum = row.dataset.verse;
            const ref = `${bookId} ${chapterNum}:${vNum}`;
            const tags = (this.verseLookup[ref] || []).concat(this.naslagVoor(ref));
            if (tags.length === 0) return;

            const numCell = row.querySelector('.verse-num');
            if (!numCell) return;

            // Verwijder bestaande tag-labels
            numCell.querySelectorAll('.verse-tag').forEach(t => t.remove());

            for (const tag of tags) {
                const dot = document.createElement('span');
                dot.className = 'verse-tag';
                dot.style.backgroundColor = tag.kleur;
                // Een naslagingang draagt zijn categorie in de tooltip, want
                // "Ree" alleen zegt niet waar je terechtkomt.
                dot.title = tag.naslagUrl ? tag.categorieLabel + ': ' + tag.naam : tag.naam;
                dot.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (tag.naslagUrl) window.location.href = tag.naslagUrl;
                    else this.showTagVerzen(tag);
                });
                numCell.appendChild(dot);
            }
        });
    },

    // Toon alle verzen van een tag in een modal
    showTagVerzen(tag) {
        let modal = document.getElementById('tag-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'tag-modal';
            modal.style.cssText = 'display:flex;position:fixed;inset:0;background:rgba(20,46,66,0.85);z-index:500;align-items:center;justify-content:center;';
            modal.onclick = (e) => { if (e.target === modal) modal.style.display = 'none'; };
            document.body.appendChild(modal);
        }

        // Sorteer op rang (1 = sleuteltekst, 2 = belangrijk, 3 = aanvullend)
        const sorted = [...tag.verzen]
            .map(item => typeof item === 'string' ? {ref: item, rang: 3} : item)
            .sort((a, b) => (a.rang || 3) - (b.rang || 3));

        const verzenHtml = sorted.map(item => {
            const ref = item.ref;
            const [book, chv] = ref.split(' ');
            const rang = item.rang || 3;
            const notitie = item.notitie || '';
            const star = rang === 1 ? '<span style="color:var(--gold);margin-right:4px;">&#9733;</span>' : '';
            const noteHtml = notitie ? `<div style="font-size:12px;color:#666;margin-top:2px;font-style:italic;">${notitie}</div>` : '';
            return `<li style="margin-bottom:10px;${rang === 1 ? 'font-weight:600;' : ''}">
                ${star}<a href="#${book}/${chv.split(':')[0]}"
                   onclick="document.getElementById('tag-modal').style.display='none'"
                   style="color:var(--gold);text-decoration:none;">
                    ${ref}
                </a>
                ${noteHtml}
            </li>`;
        }).join('');

        modal.innerHTML = `
            <div style="background:#fff;border-radius:8px;max-width:500px;width:90%;max-height:80vh;overflow-y:auto;padding:24px;box-shadow:0 8px 32px rgba(0,0,0,0.3);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                    <h2 style="font-size:20px;color:var(--navy);margin:0;">
                        <span style="color:${tag.kleur};">&#9679;</span> ${tag.naam}
                    </h2>
                    <button onclick="document.getElementById('tag-modal').style.display='none'"
                            style="border:none;background:none;font-size:24px;cursor:pointer;color:#999;">&times;</button>
                </div>
                <p style="color:#666;font-size:14px;margin-bottom:16px;">${tag.beschrijving}</p>
                <ul style="list-style:none;padding:0;">${verzenHtml}</ul>
            </div>
        `;
        modal.style.display = 'flex';
    },

    // Voeg een tag toe aan een vers (opslaan in tags.json)
    async addTag(bookId, chapterNum, verseNum, tagNaam) {
        await this.ensureLoaded();
        const ref = `${bookId} ${chapterNum}:${verseNum}`;

        // Zoek bestaande tag of maak nieuwe
        let tag = this.data.tags.find(t => t.naam === tagNaam);
        if (!tag) {
            tag = {
                id: tagNaam.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
                naam: tagNaam,
                beschrijving: '',
                kleur: '#' + Math.floor(Math.random() * 0xFFFFFF).toString(16).padStart(6, '0'),
                verzen: []
            };
            this.data.tags.push(tag);
        }

        if (!tag.verzen.some(v => (typeof v === 'string' ? v : v.ref) === ref)) {
            tag.verzen.push({ref: ref, rang: 2});
        }

        this.buildLookup();

        // Sla op (POST naar server of localStorage)
        localStorage.setItem('ov_tags', JSON.stringify(this.data));
        console.log(`Tag "${tagNaam}" toegevoegd aan ${ref}`);
    },

    // Tag-invoer popup bij een vers
    async showAddTagPopup(bookId, chapterNum, verseNum, anchorEl) {
        // De tags komen niet meer vanzelf mee met elk hoofdstuk (zie renderTagsForChapter).
        await this.ensureLoaded();
        let popup = document.getElementById('tag-add-popup');
        if (!popup) {
            popup = document.createElement('div');
            popup.id = 'tag-add-popup';
            popup.style.cssText = 'position:absolute;z-index:600;background:#fff;border:1px solid #e5e1d8;border-radius:8px;padding:12px;box-shadow:0 4px 16px rgba(0,0,0,0.15);width:250px;';
            document.body.appendChild(popup);
        }

        // Bestaande tags als suggesties
        const suggestions = this.data.tags.map(t =>
            `<button onclick="Tags.addTag('${bookId}',${chapterNum},${verseNum},'${t.naam}');document.getElementById('tag-add-popup').style.display='none';Tags.renderTagsForChapter('${bookId}',${chapterNum})"
                    style="display:inline-block;margin:2px;padding:3px 8px;border:1px solid ${t.kleur};color:${t.kleur};border-radius:12px;background:none;cursor:pointer;font-size:11px;">${t.naam}</button>`
        ).join('');

        popup.innerHTML = `
            <div style="font-size:13px;font-weight:600;margin-bottom:8px;">Tag toevoegen</div>
            <input type="text" id="tag-new-input" placeholder="Nieuwe tag..."
                   style="width:100%;padding:6px 10px;border:1px solid #ddd;border-radius:4px;font-size:13px;margin-bottom:8px;"
                   onkeydown="if(event.key==='Enter'){Tags.addTag('${bookId}',${chapterNum},${verseNum},this.value);document.getElementById('tag-add-popup').style.display='none';Tags.renderTagsForChapter('${bookId}',${chapterNum})}">
            ${suggestions ? '<div style="margin-top:4px;">' + suggestions + '</div>' : ''}
        `;

        const rect = anchorEl.getBoundingClientRect();
        popup.style.left = (rect.right + window.scrollX + 8) + 'px';
        popup.style.top = (rect.top + window.scrollY) + 'px';
        popup.style.display = 'block';

        const close = (e) => {
            if (!popup.contains(e.target)) {
                popup.style.display = 'none';
                document.removeEventListener('click', close);
            }
        };
        setTimeout(() => document.addEventListener('click', close), 10);
        setTimeout(() => document.getElementById('tag-new-input')?.focus(), 50);
    }
};

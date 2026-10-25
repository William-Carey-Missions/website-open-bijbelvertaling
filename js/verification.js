/* Account-linked verification. No assignments; the authenticated click is the record. */
(function () {
    'use strict';
    const ERROR = 'Er is een fout opgetreden. Controleer het logboek.';
    const chapters = new Map();
    const controls = new Set();
    const contents = new Map();
    let generation = 0;

    async function loadJSON(url) {
        const book = String(url).match(/(?:^|\/)data\/([^/]+)\//)?.[1];
        const response = await fetch(url, { cache: 'no-cache' });
        if (!response.ok) throw new Error(ERROR);
        if ((window.ReaderPolicy?.publicationReviewed || window.ReaderPolicy?.isNewTestament(book))) return response.json();
        const bytes = await response.arrayBuffer();
        const digest = await crypto.subtle.digest('SHA-256', bytes);
        const hash = Array.from(new Uint8Array(digest), n => n.toString(16).padStart(2, '0')).join('');
        const data = JSON.parse(new TextDecoder().decode(bytes));
        data._verificationSourceHash = hash;
        if (Array.isArray(data.verses)) {
            const chapter = await ReviewComponents.revisions('text-chapter', data);
            const verses = Object.fromEntries(await Promise.all(data.verses.map(async verse =>
                [verse.number, await ReviewComponents.revisions('text-verse', verse)])));
            contents.set(hash, { chapter, verses });
        }
        return data;
    }

    async function subject(type, id) {
        const path = '/subject?' + new URLSearchParams({ type, id });
        if (window.Collaboration && Collaboration.currentUser) return (await Collaboration.api(path)).subject;
        const response = await fetch('/api/collaboration' + path, { cache: 'no-store' });
        if (!response.ok) throw new Error(ERROR);
        return (await response.json()).subject;
    }

    function canVerify() {
        return window.Collaboration && Collaboration.hasRole('reviewer');
    }

    function administrator() {
        return window.Collaboration && Collaboration.hasRole('administrator');
    }

    function label(state) {
        if (state.status === 'correction-needed') return 'Aanpassing nodig';
        if (state.status === 'approved') return 'Geverifieerd';
        if (!canVerify()) return state.additionsOnly ? 'Toevoegingen niet geverifieerd' : 'Nog niet geverifieerd';
        return state.needsReverification ? 'Opnieuw verifiëren' : 'Verifiëren';
    }

    function render(control) {
        const { node, state } = control;
        node.replaceChildren();
        if (!state) return;
        node.hidden = control.compact && !canVerify();
        if (node.hidden) return;
        const matches = control.sourceHash === state.metadata.sourceHash;
        const parts = VerificationDisplay.parts(control);
        const localEdits = control.localCheck && control.localCheck(Object.keys(parts));
        const selected = Object.values(parts);
        const approved = selected.length > 0 && !localEdits && selected.every(part => !part.stale && part.status === 'approved');
        const displayState = { status: approved ? 'approved' : selected.some(p => p.status === 'correction-needed')
            ? 'correction-needed' : 'pending', needsReverification: selected.some(p => p.needsReverification),
            additionsOnly: parts.text?.status === 'approved' && !parts.text.stale };
        node.dataset.status = approved ? 'approved' : 'pending';
        const actionLabel = !matches ? 'Gegevens gewijzigd — herlaad'
            : localEdits ? 'Lokale bewerkingen — niet geverifieerd' : label(displayState);
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = control.compact ? (approved ? '✓' : '○') : actionLabel;
        button.setAttribute('aria-label', actionLabel + ': ' + state.label);
        button.title = actionLabel + ': ' + state.label + ' — ' + ReviewComponents.join(Object.keys(parts));
        button.disabled = !canVerify() || !matches || control.busy || approved || localEdits
            || !selected.length || displayState.status === 'correction-needed';
        if (!matches) button.title = 'De gegevens zijn gewijzigd. Herlaad deze pagina.';
        if (localEdits) button.title = 'Lokale bewerkingen kunnen niet als gepubliceerde tekst worden geverifieerd.';
        button.addEventListener('click', () => decide(control, 'approved'));
        node.appendChild(button);
        const details = document.createElement('span');
        details.className = 'verification-details';
        node.appendChild(details);
        if (control.compact && canVerify()) {
            const menu = document.createElement('button');
            menu.type = 'button';
            menu.textContent = '⋯';
            menu.setAttribute('aria-label', 'Beoordelingsacties: ' + state.label);
            menu.title = 'Beoordelingsacties';
            menu.addEventListener('click', () => menu.focus());
            node.insertBefore(menu, details);
        }
        if (canVerify() && matches && !localEdits) {
            const correction = document.createElement('a');
            correction.className = 'verification-correction';
            correction.textContent = 'Aanpassing aanvragen';
            correction.href = '/correcties.html?' + new URLSearchParams({ type: control.type, subject: control.id,
                revision: state.revision, sourceHash: control.sourceHash });
            details.appendChild(correction);
            for (const task of state.corrections) {
                const link = document.createElement('a');
                link.textContent = 'Correctietaak: ' + ReviewComponents.correctionLabel(task);
                link.href = '/correcties.html?id=' + task.id;
                details.appendChild(link);
            }
        }
        const authors = new Map();
        if (!localEdits && administrator()) for (const [key, part] of Object.entries(parts)) {
            if (part.stale || !part.latestReview) continue;
            const review = part.latestReview;
            if (!authors.has(review.id)) authors.set(review.id, { review, keys: [] });
            authors.get(review.id).keys.push(key);
        }
        for (const { review, keys } of authors.values()) {
            const author = document.createElement('span');
            author.className = 'verification-author';
            author.textContent = ReviewComponents.join(keys) + ': ' + Collaboration.reviewActorLabel(review) + ' · '
                + Collaboration.reviewDateLabel(review);
            details.appendChild(author);
        }
        if (control.onlyComponents) {
            const warning = document.createElement('span');
            warning.className = 'verification-component-warning';
            warning.textContent = ReviewComponents.warning(parts);
            node.appendChild(warning);
        }
        if (approved && canVerify()) {
            const revoke = document.createElement('button');
            revoke.type = 'button';
            revoke.textContent = 'Intrekken';
            revoke.className = 'verification-revoke';
            revoke.disabled = !matches || control.busy;
            revoke.addEventListener('click', () => decide(control, 'revoked'));
            details.appendChild(revoke);
        }
        if (control.message) {
            const message = document.createElement('span');
            message.className = 'verification-message';
            message.textContent = control.message;
            message.setAttribute('role', 'status');
            details.appendChild(message);
        }
        if (control.type === 'text-chapter') {
            const chapter = chapters.get(control.id);
            if (chapter) {
                const text = state.components.text;
                chapter.approved = text.status === 'approved' && control.revisions.text === text.revision && !control.localCheck(['text']);
                chapter.control = control;
                chapter.error = '';
            }
            if (typeof App !== 'undefined' && Navigation.currentBook + '/' + Navigation.currentChapter === control.id) {
                App._setTitle(Navigation.currentBook, Navigation.currentChapter);
                App._updateVerifiedBanner(Navigation.currentBook, Navigation.currentChapter);
            }
            if (typeof Lees !== 'undefined' && Lees.currentBook + '/' + Lees.currentChapter === control.id) {
                Lees.updateHeading(Lees._bookObj, Lees.currentChapter);
                Lees._updateVerifiedBanner(Lees.currentBook, Lees.currentChapter);
            }
        }
    }

    async function refresh(control) {
        if (control.compact && !canVerify()) {
            control.node.hidden = true;
            return;
        }
        const requestGeneration = generation;
        try {
            const state = await subject(control.type, control.id);
            if (generation !== requestGeneration || !control.node.isConnected) return;
            control.state = state;
            render(control);
        } catch (error) {
            console.error('[verification]', error);
            if (generation !== requestGeneration || !control.node.isConnected) return;
            control.node.textContent = 'Verificatiestatus niet beschikbaar.';
            if (control.type === 'text-chapter') {
                chapters.get(control.id).error = 'Verificatiestatus niet beschikbaar. Herlaad om het opnieuw te proberen.';
                const [book, chapter] = control.id.split('/');
                VerificationDisplay.banner(book, Number(chapter), control.reader);
            }
        }
    }

    async function decide(control, decision) {
        if (control.busy) return;
        if (decision === 'approved' && control.localCheck && control.localCheck(VerificationDisplay.keys(control))) {
            control.message = 'Lokale bewerkingen kunnen niet als gepubliceerde tekst worden geverifieerd.';
            render(control);
            return;
        }
        const requestGeneration = generation;
        control.busy = true;
        control.message = '';
        render(control);
        try {
            const result = await Collaboration.api('/reviews', {
                method: 'POST',
                body: JSON.stringify({
                    subjectType: control.type, subjectId: control.id,
                    revision: control.state.revision,
                    sourceHash: control.sourceHash,
                    components: Object.fromEntries(VerificationDisplay.keys(control)
                        .map(key => [key, control.state.components[key].revision])),
                    decision, note: ''
                })
            });
            if (generation !== requestGeneration || !control.node.isConnected) return;
            control.state = result.subject;
            for (const other of controls) {
                if (other !== control && (other.id === control.id || other.id.startsWith(control.id + '/')
                    || control.id.startsWith(other.id + '/'))) refresh(other);
            }
            control.message = decision === 'approved' ? 'Verificatie opgeslagen.' : 'Verificatie ingetrokken.';
            window.dispatchEvent(new CustomEvent('ov:verification-changed', { detail: {
                type: control.type, id: control.id, status: control.state.status
            } }));
        } catch (error) {
            console.error('[verification]', error);
            if (generation !== requestGeneration || !control.node.isConnected) return;
            control.message = error.status === 409
                ? 'De gegevens zijn gewijzigd. Herlaad deze pagina en controleer ze opnieuw.' : ERROR;
        } finally {
            control.busy = false;
            if (generation === requestGeneration && control.node.isConnected) render(control);
        }
    }

    function mount(parent, type, id, options = {}) {
        const key = type + ':' + id;
        let node = Array.from(parent.children).find(child => child.dataset.verification === key);
        if (node) return;
        node = document.createElement('span');
        node.className = 'ov-verification' + (options.compact ? ' verification-compact' : '');
        node.dataset.verification = key;
        node.dataset.sourceHash = options.sourceHash;
        // A verification click must not also select, edit or navigate a verse.
        ['click', 'pointerdown', 'pointerup'].forEach(event => {
            node.addEventListener(event, e => e.stopPropagation());
        });
        parent.appendChild(node);
        const loaded = contents.get(options.sourceHash);
        const revisions = type === 'text-chapter' ? loaded.chapter
            : type === 'text-verse' ? loaded.verses[id.split('/')[2]] : null;
        const control = { node, type, id, ...options, revisions, compact: !!options.compact };
        if (options.localCheck) control.localCheck = keys => options.localCheck(keys, id.split('/')[2]);
        if (control.compact) node.tabIndex = 0;
        controls.add(control);
        refresh(control);
    }

    function heading(book, chapter, reader = false) {
        if ((window.ReaderPolicy?.publicationReviewed || window.ReaderPolicy?.isNewTestament(book))) { document.getElementById('chapter-verification')?.remove(); return; }
        const options = chapters.get(book + '/' + chapter);
        const current = document.querySelector('#chapter-verification [data-verification]');
        if (current && options && current.dataset.verification === 'text-chapter:' + book + '/' + chapter
            && current.dataset.sourceHash === options.sourceHash) return;
        document.getElementById('chapter-verification')?.remove();
        if (!reader && typeof TekstEditie !== 'undefined' && TekstEditie.code() !== 'nl-ov') return;
        if (!options) return;
        const heading = document.getElementById(reader ? 'chapter-heading' : 'chapter-title');
        const slot = document.createElement('div');
        slot.id = 'chapter-verification';
        heading.after(slot);
        mount(slot, 'text-chapter', book + '/' + chapter, options);
    }

    function readerRendered(book, chapter, reader, sourceHash, continuous = false) {
        if ((window.ReaderPolicy?.publicationReviewed || window.ReaderPolicy?.isNewTestament(book))) { document.getElementById('chapter-verification')?.remove(); return; }
        if (!reader && typeof TekstEditie !== 'undefined' && TekstEditie.code() !== 'nl-ov') {
            document.getElementById('chapter-verification')?.remove();
            return;
        }
        const localCheck = (keys = ['text'], verse) => {
            const local = !reader && typeof Storage !== 'undefined' ? Storage.getEdits(book) : null;
            return !!local && Object.entries(local).some(([key, edit]) => key.startsWith(chapter + ':')
                && (!verse || key === chapter + ':' + verse)
                && ((keys.includes('text') && 'text2026' in edit) || (keys.includes('notes') && 'marginNotes' in edit)));
        };
        const options = { sourceHash, localCheck, reader };
        chapters.set(book + '/' + chapter, options);
        if (!continuous) heading(book, chapter, reader);
        const separator = document.querySelector('.chapter-separator[data-book="' + book + '"][data-chapter="' + chapter + '"]');
        if (separator) mount(separator, 'text-chapter', book + '/' + chapter, options);
        const rows = reader ? document.querySelectorAll('#verses .verse-span')
            : document.querySelectorAll('.verse-row[data-book="' + book + '"][data-chapter="' + chapter + '"]');
        rows.forEach(row => {
            const parent = reader ? row : row.querySelector('.verse-num').parentElement;
            mount(parent, 'text-verse', book + '/' + chapter + '/' + row.dataset.verse, { ...options, compact: true });
        });
        for (const control of controls) if (!control.node.isConnected) controls.delete(control);
    }

    async function refreshAll() {
        generation++;
        const current = [];
        for (const control of controls) {
            if (!control.node.isConnected) { controls.delete(control); continue; }
            // Clear identities synchronously, before requesting data for a new account.
            control.state = null;
            control.message = '';
            control.node.replaceChildren();
            current.push(control);
        }
        if (window.Collaboration && !Collaboration.ready) return;
        await Promise.all(current.map(refresh));
    }

    function isChapterVerified(book, chapter) {
        const displayed = chapters.get(book + '/' + chapter);
        return displayed ? !!displayed.approved && !displayed.localCheck() : null;
    }

    function warning(book, chapter) {
        if ((window.ReaderPolicy?.publicationReviewed || window.ReaderPolicy?.isNewTestament(book))) return '';
        const displayed = chapters.get(book + '/' + chapter);
        if (displayed?.error) return displayed.error;
        if (!displayed?.control?.state || !displayed.control.node.isConnected) return '';
        const parts = VerificationDisplay.parts(displayed.control);
        for (const key of Object.keys(parts)) if (displayed.localCheck([key])) parts[key] = { status: 'pending', local: true };
        return ReviewComponents.warning(parts);
    }

    function textVisible(book, chapter) {
        const control = chapters.get(book + '/' + chapter)?.control;
        if (!control?.state) return true;
        return control.node.isConnected && VerificationDisplay.keys(control).includes('text');
    }

    function notes(parent, book, chapter, verse) {
        if ((window.ReaderPolicy?.publicationReviewed || window.ReaderPolicy?.isNewTestament(book))) return;
        mount(parent, 'text-verse', book + '/' + chapter + '/' + verse,
            { ...chapters.get(book + '/' + chapter), onlyComponents: ['notes'] });
    }

    function loadChapters(owner) {
        if (window.ReaderPolicy?.publicationReviewed) { owner.VERIFIED_CHAPTERS = {}; return Promise.resolve(); }
        if (!owner._verifiedGeladen) owner._verifiedGeladen = fetch('/api/collaboration/verified-chapters', { cache: 'no-store' })
            .then(response => { if (!response.ok) throw new Error(ERROR); return response.json(); })
            .then(data => { owner.VERIFIED_CHAPTERS = data; })
            .catch(error => { console.error('[verification]', error); owner.VERIFIED_CHAPTERS = {}; });
        return owner._verifiedGeladen;
    }

    function chapterVerified(owner, book, chapter) {
        if ((window.ReaderPolicy?.publicationReviewed || window.ReaderPolicy?.isNewTestament(book))) return true;
        const displayed = isChapterVerified(book, chapter);
        return displayed === null ? (owner.VERIFIED_CHAPTERS[book] || []).includes(chapter) : displayed;
    }

    window.Verification = { loadJSON, mount, heading, readerRendered, refreshAll, isChapterVerified,
        warning, notes, loadChapters, chapterVerified, textVisible };
    document.addEventListener('DOMContentLoaded', () => {
        VerificationDisplay.watch(() => {
            for (const control of controls) if (control.node.isConnected && control.state) render(control);
        });
        if (window.Collaboration) Collaboration.onChange(refreshAll);
        window.addEventListener('ov:verification-changed', async event => {
            if (!event.detail.type.startsWith('text-')) return;
            if (typeof App !== 'undefined') {
                App._verifiedGeladen = null;
                await App._laadVerified();
                App._setTitle(Navigation.currentBook, Navigation.currentChapter);
                App._updateVerifiedBanner(Navigation.currentBook, Navigation.currentChapter);
                document.querySelectorAll('.tree-ch-btn').forEach(button => {
                    const verified = App._isVerified(button.dataset.bookId, Number(button.dataset.chapter));
                    button.classList.toggle('unverified', !verified);
                    button.title = verified ? 'Geverifieerd' : 'Concept — nog niet handmatig gecontroleerd';
                });
            }
            if (typeof Lees !== 'undefined') {
                Lees._verifiedGeladen = null;
                await Lees._laadVerified();
                Lees.updateHeading(Lees._bookObj, Lees.currentChapter);
                Lees.renderChapterButtons(Lees._bookObj);
                Lees._updateVerifiedBanner(Lees.currentBook, Lees.currentChapter);
            }
        });
    });
})();

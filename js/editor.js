/* Statenvertaling 2026 — Editor (contenteditable + auto-save) */

const Editor = {
    activeTooltip: null,
    activeDropdown: null,

    init() {
        // Sluit tooltips/dropdowns bij klik buiten
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.note-tooltip')) this.hideTooltip();
            if (!e.target.closest('.status-dropdown') && !e.target.closest('.verse-num')) {
                this.hideStatusDropdown();
            }
        });

        // Ctrl+S om op te slaan
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                this.saveAll();
            }
            // Ctrl+← en Ctrl+→ voor navigatie
            if (e.ctrlKey && e.key === 'ArrowLeft') {
                e.preventDefault();
                Navigation.navigateRelative(-1);
            }
            if (e.ctrlKey && e.key === 'ArrowRight') {
                e.preventDefault();
                Navigation.navigateRelative(1);
            }
        });
    },

    attachVerseListeners(row, bookId, chapterNum, verse) {
        const verseNum = verse.number;
        // Auto-save bij blur (vers-cellen)
        const editables = row.querySelectorAll('.col-2026[contenteditable="true"], .col-opmerkingen[contenteditable="true"], .col-notes[contenteditable="true"]');
        editables.forEach(cell => {
            cell.addEventListener('blur', () => {
                this.saveVerse(row, bookId, chapterNum, verseNum);
            });
        });

        // Auto-save kanttekeningen hertaald bij blur
        row.querySelectorAll('.margin-note-edit').forEach(span => {
            span.addEventListener('blur', () => {
                this.saveMarginNote(bookId, chapterNum, verseNum, span);
            });
        });

        // Nootmarker klik: staat de kanttekeningenkolom rechts in beeld, dan
        // licht de noot daar op; anders (smal scherm) opent de pop-up.
        row.querySelectorAll('.note-marker').forEach(marker => {
            marker.addEventListener('click', (e) => {
                e.stopPropagation();
                if (this.toonInKolom(row, e.currentTarget.dataset.note)) return;
                this.showNoteTooltip(e.currentTarget, bookId, chapterNum, verse);
            });
        });
        // Het nummer in de kolom opent de volledige noot (met SV 1637 en controle).
        row.querySelectorAll('.col-kt .kt-m').forEach(knop => {
            knop.addEventListener('click', (e) => {
                e.stopPropagation();
                this.showNoteTooltip(e.currentTarget, bookId, chapterNum, verse);
            });
        });

        // (Status-dropdown Concept/Review/Definitief op het versnummer is
        //  uitgeschakeld — editor-functie, hoort niet in de leesweergave.)
    },

    saveVerse(row, bookId, chapterNum, verseNum) {
        const textCell = row.querySelector('.col-2026 .primary-edition') || row.querySelector('.col-2026');
        let text2026 = '';
        if (textCell) {
            const clean = textCell.cloneNode(true);
            clean.querySelectorAll('.note-marker').forEach(marker => marker.remove());
            clean.querySelectorAll('.dropcap').forEach(dropcap => {
                dropcap.replaceWith(document.createTextNode(dropcap.dataset.letter || dropcap.textContent || ''));
            });
            text2026 = clean.innerText.trim();
        }
        const opmerkingen = row.querySelector('.col-opmerkingen')?.innerText?.trim() || '';
        const aandachtspunten = row.querySelector('.col-notes')?.innerText?.trim() || '';
        const status = row.dataset.status || 'empty';

        Storage.saveVerse(bookId, chapterNum, verseNum, {
            text2026,
            opmerkingen,
            aandachtspunten,
            status
        });

        // Update cache
        if (DataLoader.cache[bookId]) {
            const ch = DataLoader.cache[bookId].chapters.find(c => c.number === chapterNum);
            if (ch) {
                const v = ch.verses.find(v => v.number === verseNum);
                if (v) {
                    v.text2026 = text2026;
                    v.opmerkingen = opmerkingen;
                    v.aandachtspunten = aandachtspunten;
                    v.status = status;
                }
            }
        }
    },

    saveMarginNote(bookId, chapterNum, verseNum, span) {
        const noteIndex = parseInt(span.dataset.noteIndex);
        const text2026 = span.innerText.trim();

        // Update cache
        if (DataLoader.cache[bookId]) {
            const ch = DataLoader.cache[bookId].chapters.find(c => c.number === chapterNum);
            if (ch) {
                const v = ch.verses.find(v => v.number === verseNum);
                if (v && v.marginNotes && v.marginNotes[noteIndex]) {
                    v.marginNotes[noteIndex].text2026 = text2026;
                }
            }
        }

        // Sla op via Storage
        const edits = Storage.getEdits(bookId) || {};
        const key = `${chapterNum}:${verseNum}`;
        if (!edits[key]) edits[key] = {};
        if (!edits[key].marginNotes) edits[key].marginNotes = {};
        edits[key].marginNotes[noteIndex] = text2026;
        localStorage.setItem(Storage.PREFIX + bookId, JSON.stringify(edits));
    },

    saveAll() {
        document.querySelectorAll('.verse-row').forEach(row => {
            const bookId = row.dataset.book;
            const ch = parseInt(row.dataset.chapter);
            const vs = parseInt(row.dataset.verse);
            this.saveVerse(row, bookId, ch, vs);
        });
        App.updateProgress();
    },

    toonInKolom(row, noteId) {
        const kolom = row && row.querySelector('.col-kt');
        if (!kolom || kolom.offsetParent === null) return false;
        const doel = [...kolom.querySelectorAll('.kt-item')].find(item => item.dataset.note === noteId);
        if (!doel) return false;
        document.querySelectorAll('.kt-item.is-actief').forEach(item => item.classList.remove('is-actief'));
        doel.classList.add('is-actief');
        doel.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        return true;
    },

    showNoteTooltip(marker, bookId, chapterNum, verse) {
        this.hideTooltip();

        const noteId = marker.dataset.note;
        const tooltip = document.createElement('div');
        tooltip.className = 'note-tooltip reviewed-notes';
        // The review concerns this verse's notes, so show the entire reviewed set.
        // Put the clicked note first, followed by the remaining notes of the verse.
        const notes = [...verse.marginNotes].sort((a, b) => Number(b.marker === noteId) - Number(a.marker === noteId));
        for (const note of notes) {
            const linkedText1637 = References.linkify(note.text1637, bookId, chapterNum);
            const linkedText2026 = note.text2026 ? References.linkify(note.text2026, bookId, chapterNum) : '';
            const item = document.createElement('section');
            item.className = 'note-popup-item';
            const label = document.createElement('div');
            label.className = 'note-label';
            label.textContent = 'Noot ' + note.marker;
            const text = document.createElement('div');
            text.innerHTML = linkedText2026 || linkedText1637;
            item.append(label, text);
            if (linkedText2026 && linkedText1637) {
                const original = document.createElement('details');
                const summary = document.createElement('summary');
                summary.textContent = 'Statenvertaling 1637';
                const originalText = document.createElement('div');
                originalText.innerHTML = linkedText1637;
                original.append(summary, originalText);
                item.appendChild(original);
            }
            tooltip.appendChild(item);
        }

        document.body.appendChild(tooltip);
        const review = document.createElement('div');
        tooltip.prepend(review);
        Verification.notes(review, bookId, chapterNum, verse.number);

        const rect = marker.getBoundingClientRect();
        const position = () => {
            tooltip.style.top = Math.max(12, Math.min(rect.bottom + 8, innerHeight - tooltip.offsetHeight - 12)) + 'px';
            tooltip.style.left = Math.max(12, Math.min(rect.left, innerWidth - tooltip.offsetWidth - 12)) + 'px';
        };
        this.tooltipResize = new ResizeObserver(position);
        this.tooltipResize.observe(tooltip);
        position();

        this.activeTooltip = tooltip;
    },

    hideTooltip() {
        if (this.activeTooltip) {
            this.tooltipResize.disconnect();
            this.activeTooltip.remove();
            this.activeTooltip = null;
        }
    },

    showStatusDropdown(target, row, bookId, chapterNum, verseNum) {
        if (window.ReaderPolicy?.publicationReviewed) return;
        this.hideStatusDropdown();

        const dropdown = document.createElement('div');
        dropdown.className = 'status-dropdown';

        const statuses = [
            { value: 'empty', label: 'Leeg' },
            { value: 'draft', label: 'Concept' },
            { value: 'review', label: 'Review' },
            { value: 'final', label: 'Definitief' },
        ];

        for (const s of statuses) {
            const btn = document.createElement('button');
            btn.className = `s-${s.value}`;
            btn.textContent = s.label;
            btn.addEventListener('click', () => {
                row.dataset.status = s.value;
                this.saveVerse(row, bookId, chapterNum, verseNum);
                this.hideStatusDropdown();
                App.updateProgress();
            });
            dropdown.appendChild(btn);
        }

        document.body.appendChild(dropdown);

        const rect = target.getBoundingClientRect();
        dropdown.style.position = 'fixed';
        dropdown.style.top = (rect.bottom + 4) + 'px';
        dropdown.style.left = rect.left + 'px';

        this.activeDropdown = dropdown;
    },

    hideStatusDropdown() {
        if (this.activeDropdown) {
            this.activeDropdown.remove();
            this.activeDropdown = null;
        }
    }
};

/* Open Vertaling — gedrag van het modale optiespaneel. */

const OptionsPanel = {
    dialog: null,
    lastTrigger: null,
    positionKey: 'ov_options_panel_position',
    dragState: null,
    optionMirrors: new Map(),

    init() {
        if (this._initialized) return;
        this.dialog = document.getElementById('sidebar-right');
        const openButtons = [
            document.getElementById('topnav-weergave'),
            document.getElementById('topnav-mobile-weergave'),
        ].filter(Boolean);
        const closeButton = document.getElementById('sidebar-right-toggle');
        if (!this.dialog || !openButtons.length || !closeButton) return;
        this._initialized = true;

        openButtons.forEach(openButton => {
            openButton.hidden = false;
            openButton.setAttribute('aria-controls', 'sidebar-right');
            openButton.setAttribute('aria-expanded', 'false');
            if (openButton.dataset.globalOptionsBound === 'true') return;
            openButton.addEventListener('click', event => {
                event.preventDefault();
                this.open(openButton);
            });
        });
        closeButton.addEventListener('click', () => this.close());
        this.buildCategoryTemplate();
        this.setupOptionSearch();

        this.dialog.addEventListener('click', event => {
            if (event.target !== this.dialog) return;
            const rect = this.dialog.getBoundingClientRect();
            const outside = event.clientX < rect.left || event.clientX > rect.right ||
                event.clientY < rect.top || event.clientY > rect.bottom;
            if (outside) this.close();
        });
        this.dialog.addEventListener('close', () => {
            openButtons.forEach(openButton => openButton.setAttribute('aria-expanded', 'false'));
            document.body.classList.remove('options-open');
            if (this.lastTrigger && this.lastTrigger.isConnected) this.lastTrigger.focus();
        });
        this.dialog.addEventListener('cancel', event => {
            event.preventDefault();
            this.close();
        });
        this.dialog.addEventListener('change', () => {
            this.syncOptionSummaries();
            this.syncOptionMirrors();
        });

        this.setupDesktopDragging();
        window.addEventListener('resize', () => this.handleViewportChange());

        this.setupZoom();
        if (new URLSearchParams(location.search).get('opties') === '1') {
            history.replaceState(null, '', location.pathname + location.hash);
            requestAnimationFrame(() => this.open(openButtons[0]));
        }
    },

    open(trigger) {
        if (!this.dialog) return;
        this.lastTrigger = trigger || document.activeElement;
        if (window.Sidebar && Sidebar._closeLeft) Sidebar._closeLeft();
        if (!this.dialog.open) this.dialog.showModal();
        this.restoreDesktopPosition();
        this.syncOptionSummaries();
        this.syncOptionMirrors();
        document.body.classList.add('options-open');
        document.querySelectorAll('#topnav-weergave, #topnav-mobile-weergave').forEach(opener => {
            opener.setAttribute('aria-expanded', 'true');
        });
        const closeButton = document.getElementById('sidebar-right-toggle');
        if (closeButton) closeButton.focus();
    },

    close() {
        if (this.dialog && this.dialog.open) this.dialog.close();
    },

    buildCategoryTemplate() {
        const body = document.getElementById('sidebar-right-body');
        if (!body || body.dataset.categoriesBuilt === 'true') return;

        const definitions = [
            {
                key: 'bronnen', label: 'Vertalingen, talen & kanttekeningen',
                selectors: [
                    '#opt-teksteditie', '#toggle-book-intro', '#toggle-chapter-intro',
                    '#toggle-strongs', '[data-toggle-col="diff"]',
                    '[data-parallel-editie]',
                    '[data-toggle-col="1637"]', '[data-toggle-col="margin1637"]',
                    '[data-optie="kolomLayout"]', '[data-toggle-col="noteDiff"]',
                    '[data-toggle-col="hebrew"]', '#toggle-hs-vers', '#toggle-contextmarkeringen',
                ],
            },
            {
                key: 'leestekst', label: 'Leestekst',
                selectors: [
                    '#toggle-citaten', '#toggle-spoor', '#toggle-doorlopend',
                    '#toggle-versnummers', '#toggle-hoofdstuknummers',
                    '#toggle-lettertype-alternatief', '[data-optie="thema"]',
                    '#opt-regelafstand', '#toggle-pericopen', '#options-zoom', '#toggle-dyslexia',
                ],
            },
            {
                key: 'theologie', label: 'Theologie',
                selectors: [
                    '#opt-boekvolgorde', '[data-option-summary="godsnaam"]',
                    '[data-option-summary="heereNT"]',
                    '[data-option-summary="otSheol"]', '[data-option-summary="jezusNaam"]',
                    '[data-option-summary="arabischeNamen"]',
                    '[data-option-summary="maatstelsel"]', '[data-option-summary="getalweergave"]',
                    '[data-option-summary="tijdrekening"]', '#toggle-apocriefe-boeken',
                    '#toggle-ethiopische-boeken',
                ],
            },
            {
                key: 'voorlezen', label: 'Voorlezen',
                selectors: ['[name="opt-stem"]', '#opt-audio-speed'],
            },
        ];

        const originalPanels = Array.from(body.querySelectorAll('.options-tabpanel'));
        definitions.forEach(definition => {
            const category = document.createElement('details');
            category.className = 'options-category';
            category.dataset.optionsCategory = definition.key;
            // Alle kopjes staan open, zodat het paneel een doorloopbare lijst is
            // en geen reeks laatjes die eerst opengeklikt moet worden.
            category.open = true;
            const summary = document.createElement('summary');
            summary.textContent = definition.label;
            const list = document.createElement('div');
            list.className = 'options-list';
            category.append(summary, list);

            definition.selectors.forEach(selector => {
                const control = body.querySelector(selector);
                if (!control) return;
                const row = control.closest('.option-row, .option-choice');
                if (row && !list.contains(row)) list.appendChild(row);
            });
            body.appendChild(category);
        });
        originalPanels.forEach(panel => panel.remove());

        const mostUsed = document.createElement('details');
        mostUsed.className = 'options-category';
        mostUsed.dataset.optionsCategory = 'meest-gebruikt';
        mostUsed.open = true;
        const mostUsedSummary = document.createElement('summary');
        mostUsedSummary.textContent = 'Meest gebruikt';
        const mostUsedList = document.createElement('div');
        mostUsedList.className = 'options-list';
        mostUsed.append(mostUsedSummary, mostUsedList);

        [
            ['teksteditie', '#opt-teksteditie'],
            ['dyslexie', '#toggle-dyslexia'],
            ['doorlopend', '#toggle-doorlopend'],
            ['godsnaam', '[data-option-summary="godsnaam"]'],
            ['thema', '[data-optie="thema"]'],
            ['regelafstand', '#opt-regelafstand'],
            ['arabische-namen', '[data-option-summary="arabischeNamen"]'],
            ['strongs', '#toggle-strongs'],
            ['verschillen', '[data-toggle-col="diff"]'],
        ].forEach(([key, selector]) => {
            const control = body.querySelector(selector);
            const row = control && control.closest('.option-row, .option-choice');
            if (row) mostUsedList.appendChild(this.createOptionMirror(key, row));
        });
        // Het zoekveld blijft bovenaan; Meest gebruikt komt er direct onder.
        const searchField = body.querySelector('.options-search');
        if (searchField) searchField.after(mostUsed); else body.prepend(mostUsed);
        body.dataset.categoriesBuilt = 'true';
        this.syncOptionMirrors();
    },

    setupOptionSearch() {
        const search = document.getElementById('options-search');
        if (!search || search.dataset.bound === 'true') return;
        search.dataset.bound = 'true';
        const empty = document.getElementById('options-search-empty');
        search.addEventListener('input', () => {
            const query = search.value.trim().toLocaleLowerCase('nl');
            let found = 0;
            this.dialog.querySelectorAll('details.options-category').forEach(category => {
                const rows = Array.from(category.querySelectorAll(
                    ':scope > .options-list > .option-row, :scope > .options-list > .option-choice'
                ));
                if (!query) {
                    category.hidden = false;
                    rows.forEach(row => { row.hidden = false; });
                    return;
                }
                // Meest gebruikt bevat alleen kopieën; bij zoeken staat elke instelling één keer in beeld.
                if (category.dataset.optionsCategory === 'meest-gebruikt') {
                    category.hidden = true;
                    return;
                }
                const categoryMatch = category.querySelector(':scope > summary')
                    .textContent.toLocaleLowerCase('nl').includes(query);
                let visibleRows = 0;
                rows.forEach(row => {
                    const matches = categoryMatch || row.textContent.toLocaleLowerCase('nl').includes(query);
                    row.hidden = !matches;
                    if (matches) visibleRows += 1;
                });
                category.hidden = visibleRows === 0;
                if (visibleRows) category.open = true;
                found += visibleRows;
            });
            if (empty) empty.hidden = !query || found > 0;
        });
    },

    createOptionMirror(key, primaryRow) {
        const mirror = primaryRow.cloneNode(true);
        mirror.classList.add('option-mirror');
        mirror.dataset.optionMirror = key;
        mirror.removeAttribute('data-option-summary');

        mirror.querySelectorAll('[id]').forEach(element => element.removeAttribute('id'));
        mirror.querySelectorAll('[for]').forEach(element => element.removeAttribute('for'));
        mirror.querySelectorAll('[aria-controls], [aria-describedby], [aria-labelledby]').forEach(element => {
            element.removeAttribute('aria-controls');
            element.removeAttribute('aria-describedby');
            element.removeAttribute('aria-labelledby');
        });

        const primaryControls = Array.from(primaryRow.querySelectorAll('input, select'));
        const mirrorControls = Array.from(mirror.querySelectorAll('input, select'));
        mirrorControls.forEach((control, index) => {
            control.removeAttribute('onchange');
            control.removeAttribute('data-optie');
            control.removeAttribute('data-toggle-col');
            if (control.type === 'radio') control.name = `option-mirror-${key}-${control.name}`;
            control.addEventListener('change', () => {
                const primary = primaryControls[index];
                if (!primary || (control.type === 'radio' && !control.checked)) return;
                if (control.type === 'checkbox' || control.type === 'radio') {
                    primary.checked = control.checked;
                } else {
                    primary.value = control.value;
                }
                primary.dispatchEvent(new Event('change', { bubbles: true }));
                this.syncOptionMirrors();
            });
        });

        this.optionMirrors.set(key, { primaryRow, mirror });
        return mirror;
    },

    syncOptionMirrors() {
        this.optionMirrors.forEach(({ primaryRow, mirror }) => {
            const primaryControls = Array.from(primaryRow.querySelectorAll('input, select'));
            const mirrorControls = Array.from(mirror.querySelectorAll('input, select'));
            mirrorControls.forEach((control, index) => {
                const primary = primaryControls[index];
                if (!primary) return;
                if (control.type === 'checkbox' || control.type === 'radio') {
                    control.checked = primary.checked;
                } else {
                    control.value = primary.value;
                }
            });

            const current = mirror.querySelector('.option-current');
            const selected = mirror.querySelector('input:checked, option:checked');
            if (current && selected) {
                const label = selected.closest('label');
                current.textContent = label ? label.textContent.trim() : selected.textContent.trim();
            }
        });
    },

    isDesktop() {
        return window.matchMedia('(min-width: 769px)').matches;
    },

    setupDesktopDragging() {
        const header = document.getElementById('sidebar-right-header');
        if (!header) return;

        header.addEventListener('pointerdown', event => {
            if (!this.isDesktop() || event.button !== 0) return;
            if (event.target.closest('button, input, select, textarea, a, [role="tab"]')) return;

            const rect = this.dialog.getBoundingClientRect();
            this.dragState = {
                pointerId: event.pointerId,
                offsetX: event.clientX - rect.left,
                offsetY: event.clientY - rect.top,
            };
            this.dialog.classList.add('is-dragging');
            header.setPointerCapture(event.pointerId);
            event.preventDefault();
        });

        header.addEventListener('pointermove', event => {
            if (!this.dragState || event.pointerId !== this.dragState.pointerId) return;
            this.setDesktopPosition(
                event.clientX - this.dragState.offsetX,
                event.clientY - this.dragState.offsetY,
            );
        });

        const finishDrag = event => {
            if (!this.dragState || event.pointerId !== this.dragState.pointerId) return;
            if (header.hasPointerCapture(event.pointerId)) header.releasePointerCapture(event.pointerId);
            this.dragState = null;
            this.dialog.classList.remove('is-dragging');
            this.saveDesktopPosition();
        };
        header.addEventListener('pointerup', finishDrag);
        header.addEventListener('pointercancel', finishDrag);
    },

    clampDesktopPosition(x, y) {
        const rect = this.dialog.getBoundingClientRect();
        const padding = 16;
        const maxX = Math.max(padding, window.innerWidth - rect.width - padding);
        const maxY = Math.max(padding, window.innerHeight - rect.height - padding);
        return {
            x: Math.min(Math.max(x, padding), maxX),
            y: Math.min(Math.max(y, padding), maxY),
        };
    },

    setDesktopPosition(x, y) {
        if (!this.isDesktop()) return;
        this.dialog.classList.add('has-custom-position');
        const position = this.clampDesktopPosition(x, y);
        Object.assign(this.dialog.style, {
            left: `${position.x}px`,
            top: `${position.y}px`,
            right: 'auto',
            bottom: 'auto',
        });
    },

    saveDesktopPosition() {
        if (!this.isDesktop()) return;
        const rect = this.dialog.getBoundingClientRect();
        const position = this.clampDesktopPosition(rect.left, rect.top);
        localStorage.setItem(this.positionKey, JSON.stringify(position));
    },

    readDesktopPosition() {
        try {
            const position = JSON.parse(localStorage.getItem(this.positionKey));
            if (!position || !Number.isFinite(position.x) || !Number.isFinite(position.y)) return null;
            return position;
        } catch (_error) {
            return null;
        }
    },

    restoreDesktopPosition() {
        if (!this.isDesktop()) {
            this.clearInlinePosition();
            return;
        }
        const position = this.readDesktopPosition();
        if (position) this.setDesktopPosition(position.x, position.y);
    },

    clearInlinePosition() {
        this.dialog.classList.remove('has-custom-position');
        this.dialog.style.removeProperty('left');
        this.dialog.style.removeProperty('top');
        this.dialog.style.removeProperty('right');
        this.dialog.style.removeProperty('bottom');
    },

    handleViewportChange() {
        if (!this.dialog || !this.dialog.open) return;
        if (!this.isDesktop()) {
            this.clearInlinePosition();
            return;
        }
        const position = this.readDesktopPosition();
        if (position) this.setDesktopPosition(position.x, position.y);
    },

    setupZoom() {
        const bind = () => {
            if (!window.OVZoom || this.dialog.dataset.zoomBound === 'true') return;
            const out = document.getElementById('options-zoom-out');
            const value = document.getElementById('options-zoom-value');
            const input = document.getElementById('options-zoom-in');
            if (!out || !value || !input) return;
            this.dialog.dataset.zoomBound = 'true';
            out.addEventListener('click', () => OVZoom.step(-1));
            input.addEventListener('click', () => OVZoom.step(1));
            value.addEventListener('click', () => OVZoom.reset());
            OVZoom.subscribe(zoom => {
                value.textContent = `${Math.round(zoom * 100)}%`;
            });
        };
        bind();
        window.addEventListener('ovzoomready', bind, { once: true });
    },

    syncOptionSummaries() {
        if (!this.dialog) return;
        this.dialog.querySelectorAll('[data-option-summary]').forEach(group => {
            const option = group.dataset.optionSummary;
            const checked = group.querySelector(`[data-optie="${option}"]:checked`);
            const current = group.querySelector('.option-current');
            if (!checked || !current) return;
            const label = checked.closest('label');
            current.textContent = label ? label.textContent.trim() : checked.value;
        });
    },
};

window.OptionsPanel = OptionsPanel;
document.addEventListener('DOMContentLoaded', () => OptionsPanel.init());

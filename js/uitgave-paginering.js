/* Gemeten papierpagina's: tekst boven en kanttekeningen onder dezelfde pagina. */
window.OVUitgavePaginering = async function (doc, signal, progress) {
    await doc.fonts.ready;
    const chapters = [...doc.querySelectorAll('.chapter')];
    let pageNumber = doc.querySelector('.cover') ? 1 : 0;
    const cancelled = () => { if (signal.aborted) throw new DOMException('Geannuleerd', 'AbortError'); };
    function overflow(el) {
        return el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1;
    }
    function page(title, before) {
        const el = doc.createElement('article'); el.className = 'paper';
        const head = doc.createElement('header'); head.className = 'running'; head.textContent = title;
        const body = doc.createElement('div'); body.className = 'paper-body';
        const scripture = doc.createElement('div'); scripture.className = 'scripture';
        const notes = doc.createElement('aside'); notes.className = 'page-notes';
        const footer = doc.createElement('footer'); footer.textContent = String(++pageNumber);
        body.append(scripture, notes); el.append(head, body, footer); before.before(el);
        return {el, body, scripture, notes};
    }
    function fit(p) {
        const available = p.body.clientHeight;
        if (p.notes.childElementCount) {
            p.notes.hidden = false;
            // Minimale hoogte waarbij drie nootkolommen niet horizontaal overlopen.
            let lo = 1, hi = available;
            while (hi - lo > 1) {
                const mid = Math.ceil((lo + hi) / 2); p.notes.style.height = mid + 'px';
                if (overflow(p.notes)) lo = mid; else hi = mid;
            }
            p.notes.style.height = (hi + 2) + 'px';
            p.scripture.style.height = Math.max(0, available - hi - 14) + 'px';
        } else {
            p.notes.hidden = true; p.scripture.style.height = available + 'px';
        }
        return !overflow(p.scripture) && (!p.notes.childElementCount || !overflow(p.notes)) && p.scripture.clientHeight >= 0 && p.body.scrollHeight <= available + 1;
    }
    // Splits een uitzonderlijk lange tekst/noot zonder opmaak of woorden te verliezen.
    function split(block, chars) {
        const walker = doc.createTreeWalker(block, 4); const nodes = []; let n, length = 0;
        while ((n = walker.nextNode())) { nodes.push({node:n,start:length}); length += n.length; }
        let cut = Math.min(chars, length);
        const text = block.textContent;
        while (cut > 0 && cut < length && !/\s/.test(text[cut - 1])) cut--;
        if (!cut) return null;
        const point = nodes.find(x => cut <= x.start + x.node.length);
        if (!point) return null;
        const range = doc.createRange(); range.selectNodeContents(block);
        range.setEnd(point.node, cut - point.start);
        const first = block.cloneNode(false); first.append(range.cloneContents());
        range.selectNodeContents(block); range.setStart(point.node, cut - point.start);
        const rest = block.cloneNode(false); rest.append(range.cloneContents());
        return {first,rest,length:cut};
    }
    function placeLong(p, block, target, next) {
        let remainder = block;
        while (remainder.textContent.trim()) {
            cancelled();
            const area = target(p); area.append(remainder);
            if (fit(p)) return p;
            remainder.remove();
            let lo = 0, hi = remainder.textContent.length, best = null;
            while (hi - lo > 1) {
                const mid = Math.floor((lo + hi) / 2), candidate = split(remainder, mid);
                if (!candidate) { lo = mid; continue; }
                area.append(candidate.first); const ok = fit(p); candidate.first.remove();
                if (ok) { lo = mid; best = candidate; } else hi = mid;
            }
            if (!best) {
                if (!p.scripture.childElementCount && !p.notes.childElementCount) throw Error('Deze lettergrootte past niet op het gekozen papier. Kies een kleinere letter of A4.');
                p = next(); continue;
            }
            area.append(best.first); fit(p); remainder = best.rest;
            if (remainder.textContent.trim()) p = next();
        }
        return p;
    }
    for (let index = 0; index < chapters.length; index++) {
        cancelled(); const chapter = chapters[index]; const title = chapter.querySelector('h2').textContent;
        const verses = [...chapter.querySelectorAll('.scripture > .vers')];
        const notes = [...chapter.querySelectorAll('aside > p')];
        const next = () => page(title + ' · vervolg', chapter);
        let p = page(title, chapter);
        for (const verse of verses) {
            const linked = notes.filter(n => n.dataset.verse === verse.dataset.verse);
            const text = verse.cloneNode(true), annotations = linked.map(n => n.cloneNode(true));
            p.scripture.append(text); p.notes.append(...annotations);
            if (fit(p)) continue;
            text.remove(); annotations.forEach(n => n.remove()); fit(p);
            if (p.scripture.childElementCount || p.notes.childElementCount) p = next();
            p.scripture.append(text); p.notes.append(...annotations);
            if (fit(p)) continue;
            // Een heel vers met zijn noten past niet: behoud de tekst en vervolg lange noten.
            text.remove(); annotations.forEach(n => n.remove());
            p = placeLong(p, text, x => x.scripture, next);
            for (const note of annotations) p = placeLong(p, note, x => x.notes, next);
        }
        chapter.remove();
        progress(index + 1, chapters.length);
        await new Promise(resolve => setTimeout(resolve, 0));
    }
};

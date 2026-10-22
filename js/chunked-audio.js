/* Open Vertaling — chunk-audio speler
 * ------------------------------------------------------------------
 * Speelt een hoofdstuk af uit LOSSE audio-segmenten (chunks) op basis van een
 * manifest, zodat godsnaam (HEERE/JAHWEH/Jehova), kopjes en de boekaankondiging
 * optioneel zijn. Zie docs/superpowers/specs/2026-07-15-chunked-audio-design.md.
 *
 * Volledig achterwaarts compatibel: is er voor een hoofdstuk geen manifest, dan
 * geeft load() null terug en valt de aanroeper terug op de losse-MP3-speler.
 *
 * Deze module raakt window.AUDIO_AVAILABLE NIET aan (die leeft in
 * js/audio-available.js en wordt door de TTS-sessie beheerd).
 */
(function () {
    'use strict';

    function manifestUrl(bookId, chapter, voice) {
        return window.OV_ASSETS.url(
            'audio/' + bookId + '/' + chapter + '/' + voice + '/manifest.json'
        );
    }
    function segUrl(bookId, chapter, voice, file) {
        return window.OV_ASSETS.url(
            'audio/' + bookId + '/' + chapter + '/' + voice + '/' + file
        );
    }

    // Standaardinstellingen; lezer-voorkeuren komen uit localStorage.
    function defaultSettings() {
        var s = { divineName: 'heere', headings: false, announce: true };
        try {
            var raw = localStorage.getItem('sv2026_audioChunkOpts');
            if (raw) { var o = JSON.parse(raw); for (var k in o) if (o[k] !== undefined) s[k] = o[k]; }
        } catch (e) {}
        s.divineName = 'heere';
        return s;
    }
    function saveSettings(s) {
        s.divineName = 'heere';
        try { localStorage.setItem('sv2026_audioChunkOpts', JSON.stringify(s)); } catch (e) {}
    }

    /* Haal het manifest op. Retourneert het geparste object of null (geen chunks). */
    function load(bookId, chapter, voice) {
        return fetch(manifestUrl(bookId, chapter, voice))
            .then(function (r) { return r.ok ? r.json() : null; })
            .catch(function () { return null; });
    }

    /* Zuivere functie: bouw de afspeellijst uit het manifest + instellingen.
     * Elk item: { type, verse?, src, dur, text? }. Eenvoudig te unit-testen. */
    function buildPlaylist(manifest, settings) {
        var s = settings || defaultSettings();
        var out = [];
        var segs = (manifest && manifest.segments) || [];
        for (var i = 0; i < segs.length; i++) {
            var seg = segs[i];
            if (seg.type === 'intro') {
                if (s.announce !== false) out.push({ type: 'intro', src: seg.file, dur: seg.dur || 0 });
            } else if (seg.type === 'heading') {
                if (s.headings) out.push({ type: 'heading', afterVerse: seg.afterVerse, src: seg.file, dur: seg.dur || 0, text: seg.text });
            } else if (seg.type === 'verse') {
                if (seg.divineName) {
                    var key = (s.divineName || 'heere');
                    var vfile = (seg.variants && (seg.variants[key] || seg.variants.heere));
                    var vdur = (seg.dur && typeof seg.dur === 'object') ? (seg.dur[key] || seg.dur.heere || 0) : (seg.dur || 0);
                    if (vfile) out.push({ type: 'verse', verse: seg.verse, src: vfile, dur: vdur, divineName: true });
                } else {
                    out.push({ type: 'verse', verse: seg.verse, src: seg.file, dur: seg.dur || 0 });
                }
            }
        }
        return out;
    }

    function totalDuration(playlist) {
        var t = 0;
        for (var i = 0; i < playlist.length; i++) t += (playlist[i].dur || 0);
        return t;
    }

    /* Controller die de losse segmenten GAPLOOS afspeelt via de Web Audio API.
     *
     * Waarom Web Audio i.p.v. één <audio>-element dat per clip van src wisselt:
     * een hoofdstuk bestaat uit tientallen minuscule Opus-clipjes; bij het
     * sequentieel omwisselen van audioEl.src racen de load()/play()-aanroepen en
     * slaat de browser hele verzen over. Met vooraf gedecodeerde AudioBuffers die
     * we sample-nauwkeurig achter elkaar plannen (source.start(t)) is er geen
     * naad en wordt niets overgeslagen.
     *
     * Om lees.js/app.js ONGEWIJZIGD te laten (die audioEl.play()/pause()/paused
     * gebruiken en op de 'play'/'pause'-events de knop bijwerken) virtualiseren we
     * die op dit ene element: ze sturen voortaan de Web Audio-engine aan.
     *
     * callbacks: { onVerse(n), onPlay(), onPause(), onEnded(), onTime(elapsed,total) } */
    function createController(audioEl, manifest, settings, callbacks) {
        var cb = callbacks || {};
        var s = settings || defaultSettings();
        var bookId = manifest.book, chapter = manifest.chapter, voice = manifest.voice;
        var playlist = buildPlaylist(manifest, s);
        var destroyed = false;

        var AC = window.AudioContext || window.webkitAudioContext;
        var ctx = null;
        var buffers = [];        // AudioBuffer per playlist-item (null bij decode-fout)
        var segStart = [];       // cumulatieve starttijd per item (sec)
        var total = 0;
        var sources = [];        // actief geplande bronnen
        var wantPlay = false;    // gebruikersintentie (stuurt knop/paused)
        var playing = false;     // daadwerkelijk gepland
        var pausedPos = 0;       // positie (sec) waar we stilstaan
        var startCtxTime = 0;    // ctx.currentTime bij laatste (her)planning
        var startPos = 0;        // playlist-positie bij laatste (her)planning
        var tick = null;
        var lastVerse = null;
        var decodedFor = null;   // playlist waarvoor buffers/segStart gelden

        // --- audioEl virtualiseren zodat bestaande aanroepers blijven werken ---
        var pausedDesc = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'paused');
        audioEl.play = function () { ctlPlay(); return Promise.resolve(); };
        audioEl.pause = function () { ctlPause(); };
        Object.defineProperty(audioEl, 'paused', {
            configurable: true, get: function () { return !wantPlay; }
        });

        function rebuildTiming() {
            segStart = []; var t = 0;
            for (var i = 0; i < playlist.length; i++) { segStart[i] = t; t += (playlist[i].dur || 0); }
            total = t;
        }
        rebuildTiming();
        emitVerse(0);

        function ensureCtx() {
            if (!ctx) ctx = new AC();
            if (ctx.state === 'suspended' && ctx.resume) ctx.resume();
            return ctx;
        }

        function fetchDecode(src) {
            return fetch(segUrl(bookId, chapter, voice, src))
                .then(function (r) { return r.arrayBuffer(); })
                .then(function (ab) {
                    return new Promise(function (res, rej) { ctx.decodeAudioData(ab, res, rej); });
                });
        }

        // Decodeer alle segmenten van de huidige playlist (idempotent per playlist).
        function decodeAll() {
            if (decodedFor === playlist) return Promise.resolve();
            ensureCtx();
            var pl = playlist;
            return Promise.all(pl.map(function (it) {
                return fetchDecode(it.src).catch(function (e) {
                    if (window.console) console.warn('chunk-audio decode faalt:', it.src, e);
                    return null;
                });
            })).then(function (bufs) {
                if (destroyed || playlist !== pl) return;
                buffers = bufs;
                segStart = []; var t = 0;
                for (var i = 0; i < bufs.length; i++) {
                    segStart[i] = t;
                    t += (bufs[i] ? bufs[i].duration : (pl[i].dur || 0));
                }
                total = t;
                decodedFor = pl;
            });
        }

        function stopSources() {
            for (var i = 0; i < sources.length; i++) { try { sources[i].stop(); } catch (e) {} }
            sources = [];
        }

        function segIndexAt(pos) {
            for (var i = 0; i < segStart.length; i++) {
                var end = (i + 1 < segStart.length) ? segStart[i + 1] : total;
                if (pos < end) return i;
            }
            return Math.max(0, segStart.length - 1);
        }

        function curPos() { return playing ? (startPos + (ctx.currentTime - startCtxTime)) : pausedPos; }

        function emitVerse(i) {
            var it = playlist[i];
            if (it && it.type === 'verse' && it.verse !== lastVerse) {
                lastVerse = it.verse;
                if (cb.onVerse) cb.onVerse(it.verse);
            }
        }

        function startTick() {
            if (tick) return;
            tick = setInterval(function () {
                if (!playing) return;
                var pos = curPos();
                if (pos >= total - 0.02) { finish(); return; }
                emitVerse(segIndexAt(pos));
                if (cb.onTime) cb.onTime(pos, total);
            }, 200);
        }
        function stopTick() { if (tick) { clearInterval(tick); tick = null; } }

        // Plan alle segmenten vanaf positie `pos` gaploos achter elkaar.
        function scheduleFrom(pos) {
            stopSources();
            if (!buffers.length || pos >= total) { if (pos >= total) finish(); return; }
            var i0 = segIndexAt(pos);
            var off0 = pos - segStart[i0];
            var base = ctx.currentTime + 0.08;
            for (var i = i0; i < buffers.length; i++) {
                var buf = buffers[i];
                if (!buf) continue;
                var src = ctx.createBufferSource();
                src.buffer = buf;
                src.connect(ctx.destination);
                try { src.start(base + (segStart[i] - pos), i === i0 ? off0 : 0); } catch (e) {}
                sources.push(src);
            }
            startCtxTime = base; startPos = pos; playing = true;
            lastVerse = null; emitVerse(i0);
            startTick();
        }

        function finish() {
            stopSources(); stopTick();
            wantPlay = false; playing = false; pausedPos = 0; lastVerse = null;
            audioEl.dispatchEvent(new Event('pause'));
            if (cb.onEnded) cb.onEnded();
        }

        function ctlPlay() {
            if (destroyed || wantPlay) return;
            wantPlay = true;
            ensureCtx();
            audioEl.dispatchEvent(new Event('play'));
            decodeAll().then(function () {
                if (destroyed || !wantPlay || playing) return;
                scheduleFrom(pausedPos >= total ? 0 : pausedPos);
            });
        }
        function ctlPause() {
            if (!wantPlay) return;
            if (playing) pausedPos = curPos();
            stopSources(); stopTick();
            wantPlay = false; playing = false;
            audioEl.dispatchEvent(new Event('pause'));
        }

        return {
            play: ctlPlay,
            pause: ctlPause,
            isPlaying: function () { return wantPlay; },
            currentVerse: function () { var it = playlist[segIndexAt(curPos())]; return it ? it.verse : null; },
            /* Spring naar het segment dat vers N voorleest. */
            seekToVerse: function (n) {
                for (var i = 0; i < playlist.length; i++) {
                    if (playlist[i].type === 'verse' && playlist[i].verse === n) {
                        var pos = segStart[i] || 0;
                        if (wantPlay && decodedFor === playlist) scheduleFrom(pos);
                        else { pausedPos = pos; lastVerse = null; emitVerse(i); }
                        return true;
                    }
                }
                return false;
            },
            /* Pas instellingen toe (godsnaam/kopjes/intro) zonder de plek te verliezen. */
            setSettings: function (newSettings) {
                var curVerse = this.currentVerse();
                var wasPlaying = wantPlay;
                s = newSettings; saveSettings(s);
                stopSources(); stopTick(); playing = false;
                playlist = buildPlaylist(manifest, s);
                buffers = []; decodedFor = null; lastVerse = null;
                rebuildTiming();
                var target = 0;
                if (curVerse != null) {
                    for (var i = 0; i < playlist.length; i++) {
                        if (playlist[i].type === 'verse' && playlist[i].verse >= curVerse) { target = i; break; }
                    }
                }
                var pos = segStart[target] || 0;
                if (wasPlaying) {
                    wantPlay = true; ensureCtx();
                    decodeAll().then(function () { if (!destroyed && wantPlay && !playing) scheduleFrom(pos); });
                } else {
                    wantPlay = false; pausedPos = pos; emitVerse(target);
                }
            },
            playlist: function () { return playlist.slice(); },
            totalDuration: function () { return total; },
            destroy: function () {
                destroyed = true;
                stopSources(); stopTick();
                delete audioEl.play; delete audioEl.pause;
                if (pausedDesc) Object.defineProperty(audioEl, 'paused', pausedDesc);
                else try { delete audioEl.paused; } catch (e) {}
                if (ctx && ctx.close) { try { ctx.close(); } catch (e) {} }
            }
        };
    }

    window.ChunkedAudio = {
        load: load,
        buildPlaylist: buildPlaylist,
        totalDuration: totalDuration,
        createController: createController,
        defaultSettings: defaultSettings,
        saveSettings: saveSettings,
        _manifestUrl: manifestUrl
    };
})();

/* Gedeelde client voor accounts, rollen en beoordelingen. */
(function () {
    'use strict';

    var listeners = [];
    var sessionGeneration = 0;

    function emit(profile) {
        listeners.slice().forEach(function (listener) {
            try { listener(profile, Collaboration.ready); } catch (error) { console.warn('[Collaboration] listener mislukt'); }
        });
        window.dispatchEvent(new CustomEvent('ov:collaboration-ready', { detail: profile }));
    }

    async function token(forceRefresh, user) {
        if (!user) throw new Error('AUTH_REQUIRED');
        var value = await user.getIdToken(!!forceRefresh);
        if (user !== Auth.currentUser) throw new Error('AUTH_CHANGED');
        return value;
    }

    async function request(path, options, retry) {
        options = options || {};
        var user = window.Auth && Auth.currentUser;
        var headers = new Headers(options.headers || {});
        headers.set('Authorization', 'Bearer ' + await token(false, user));
        if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
        var response = await fetch('/api/collaboration' + path, Object.assign({}, options, { headers: headers, cache: 'no-store' }));
        if (response.status === 401 && retry !== false) {
            headers.set('Authorization', 'Bearer ' + await token(true, user));
            response = await fetch('/api/collaboration' + path, Object.assign({}, options, { headers: headers, cache: 'no-store' }));
        }
        var payload = await response.json().catch(function () { return {}; });
        if (!response.ok) {
            var error = new Error('Er is een fout opgetreden. Controleer het logboek.');
            error.status = response.status;
            throw error;
        }
        return payload;
    }

    function setNavigation(profile) {
        var links = document.getElementById('topnav-links');
        if (!links) return;
        ['review', 'users', 'corrections'].forEach(function (name) {
            var old = links.querySelector('[data-collaboration-link="' + name + '"]');
            if (old) old.remove();
        });
        if (!profile) return;
        if (profile.roles.indexOf('reviewer') !== -1) {
            var corrections = document.createElement('a');
            corrections.href = '/correcties.html';
            corrections.dataset.collaborationLink = 'corrections';
            corrections.textContent = 'Correctietaken';
            if (location.pathname.endsWith('/correcties.html')) corrections.classList.add('active');
            links.appendChild(corrections);
        }
        if (profile.roles.indexOf('administrator') !== -1) {
            var users = document.createElement('a');
            users.href = 'gebruikers.html';
            users.dataset.collaborationLink = 'users';
            users.textContent = 'Gebruikers';
            if (location.pathname.endsWith('/gebruikers.html')) users.classList.add('active');
            links.appendChild(users);
        }
    }

    async function synchronize(user, stateResolved) {
        if (!stateResolved) return;
        var generation = ++sessionGeneration;
        Collaboration.currentUser = null;
        Collaboration.ready = false;
        setNavigation(null);
        emit(null);
        if (!user) {
            Collaboration.currentUser = null;
            Collaboration.ready = true;
            setNavigation(null);
            emit(null);
            return;
        }
        try {
            var payload = await request('/session', { method: 'POST', body: '{}' });
            if (generation !== sessionGeneration) return;
            Collaboration.currentUser = payload.user;
            Collaboration.ready = true;
            setNavigation(payload.user);
            emit(payload.user);
        } catch (error) {
            if (generation !== sessionGeneration) return;
            Collaboration.currentUser = null;
            Collaboration.ready = true;
            setNavigation(null);
            console.warn('[Collaboration] sessie kon niet worden geladen');
            emit(null);
        }
    }

    var Collaboration = {
        currentUser: null,
        ready: false,

        init: function () {
            window.Auth.onChange(synchronize);
        },

        onChange: function (listener) {
            listeners.push(listener);
            listener(this.currentUser, this.ready);
        },

        hasRole: function (role) {
            return !!this.currentUser && this.currentUser.roles.indexOf(role) !== -1;
        },

        reviewActorLabel: function (review) {
            return review.actor.displayName + (review.actor.registered ? '' : ' (nog niet aangemeld)');
        },

        reviewDateLabel: function (review) {
            var date = new Date(review.createdAt).toLocaleString('nl-NL');
            return review.actor.kind === 'historical-import'
                ? 'Eerdere controle; controledatum onbekend. Geïmporteerd op ' + date : date;
        },

        api: function (path, options) {
            return request(path, options);
        }
    };

    window.Collaboration = Collaboration;
    window.addEventListener('pagehide', function () {
        sessionGeneration++;
        Collaboration.currentUser = null;
        Collaboration.ready = false;
        setNavigation(null);
        emit(null);
    });
    window.addEventListener('pageshow', function (event) {
        // A restored document must resolve the current login again, not reuse private DOM.
        if (event.persisted) location.reload();
    });
})();

/*
 * Anda Tayo - Map Explorer (templates/map.html)
 *
 * Data flow:
 *   1. The first batch of spots is embedded by Django as JSON  (<script id="map-initial">).
 *   2. Every filter change calls  GET /api/spots/?lat=&lng=&radius=&category=&amenity=&mood=&q=
 *      The server does the Haversine distance math and returns spots nearest-first.
 *   3. We redraw the list + the map pins, and keep the URL in sync so the view can be shared.
 *
 * Look & feel uses the shared components from static/css/style.css (.card .tag .btn .chip) and the
 * icon set from core/icons.py (sent as initial.icons), so the map matches the rest of the site.
 *
 * Safety: spot names etc. come from users, so they are only ever inserted with textContent.
 */
(function () {
    'use strict';

    var initial = JSON.parse(document.getElementById('map-initial').textContent);
    var API_URL = initial.api_url;
    var ICONS = initial.icons;

    // ---------------------------------------------------------------- state
    var f = initial.filters;
    var state = {
        lat: f.lat, lng: f.lng,                       // search origin (user or WMSU), null = none
        radius: f.radius || null,                     // km
        category: f.category || '',
        amenities: (f.amenities || []).slice(),
        mood: f.mood ? String(f.mood) : '',
        q: f.q || '',
        originLabel: f.lat != null ? 'Pinned location' : null,
    };

    // ---------------------------------------------------------------- layout: full height minus header
    var explorer = document.getElementById('explorer');
    function sizeExplorer() {
        var header = document.getElementById('site-header');
        var h = header ? header.offsetHeight : 80;
        explorer.style.height = 'calc(100dvh - ' + h + 'px)';
        if (map) map.invalidateSize();
    }

    // ---------------------------------------------------------------- map
    var map = L.map('map', {zoomControl: false}).setView(initial.default_center, 14);
    L.control.zoom({position: 'topright'}).addTo(map);
    L.tileLayer(window.ANDATAYO_MAP.tiles.url, window.ANDATAYO_MAP.tiles.options).addTo(map);

    var markersLayer = L.layerGroup().addTo(map);
    var originLayer = L.layerGroup().addTo(map);
    var markers = {};      // spot id -> marker
    var spots = initial.spots;

    function safeColor(c) { return /^#[0-9a-fA-F]{6}$/.test(c) ? c : '#6b7280'; }

    // ---------------------------------------------------------------- small DOM helpers
    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) node.className = className;
        if (text != null) node.textContent = text;
        return node;
    }

    /** Line icon from core/icons.py. The markup is our own constant, never user data. */
    function icon(name, cls) {
        var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 24 24');
        svg.setAttribute('fill', 'none');
        svg.setAttribute('stroke', 'currentColor');
        svg.setAttribute('stroke-width', '2');
        svg.setAttribute('stroke-linecap', 'round');
        svg.setAttribute('stroke-linejoin', 'round');
        svg.setAttribute('aria-hidden', 'true');
        svg.setAttribute('class', cls || 'h-4 w-4');
        svg.innerHTML = ICONS[name] || ICONS.pin;
        return svg;
    }

    function tag(text, iconName, bg, fg) {
        var t = el('span', 'tag');
        if (bg) t.style.setProperty('--tag-bg', bg);
        if (fg) t.style.setProperty('--tag-fg', fg);
        if (iconName) t.appendChild(icon(iconName, 'h-3 w-3'));
        t.appendChild(document.createTextNode(text));
        return t;
    }

    function categoryTag(spot) {
        return tag(spot.category.label, spot.category.icon, safeColor(spot.category.color), '#fff');
    }

    function distanceText(spot) {
        return spot.distance_text || spot.wmsu_text || '';
    }

    function amenityTags(spot, max) {
        var row = el('div', 'flex flex-wrap gap-1');
        spot.amenities.slice(0, max || 6).forEach(function (a) { row.appendChild(tag(a.name, a.icon)); });
        if (spot.wifi_mbps) row.appendChild(tag(spot.wifi_mbps + ' Mbps', 'wifi'));
        return row;
    }

    function thumb(spot, cls) {
        var box = el('div', cls + ' grid place-items-center overflow-hidden text-stone-700/60');
        box.style.background = safeColor(spot.mood.pastel);
        if (spot.image) {
            var img = el('img', 'h-full w-full object-cover');
            img.src = spot.image; img.alt = spot.name; img.loading = 'lazy';
            box.appendChild(img);
        } else {
            box.appendChild(icon(spot.category.icon, 'h-8 w-8'));
        }
        return box;
    }

    // ---------------------------------------------------------------- pins
    function pinIcon(spot, active) {
        var wrap = el('div', 'at-pin' + (active ? ' is-active' : ''));
        wrap.style.setProperty('--pin', safeColor(spot.category.color));
        var inner = el('span', 'at-pin__icon');
        inner.appendChild(icon(spot.category.icon));
        wrap.appendChild(inner);
        return L.divIcon({className: 'at-pin-wrap', html: wrap, iconSize: [38, 46], iconAnchor: [19, 44], popupAnchor: [0, -40]});
    }

    // ---------------------------------------------------------------- popup
    function metaLine(spot) {
        var bits = [];
        if (distanceText(spot)) bits.push(distanceText(spot));
        if (spot.rating) bits.push('★ ' + spot.rating + ' (' + spot.reviews + ')');
        bits.push(spot.price.level + ' · from ₱' + spot.price.starts_at);
        return bits.join('  ·  ');
    }

    function popupContent(spot) {
        var card = el('div', 'w-64');
        card.appendChild(thumb(spot, 'h-28 w-full rounded-xl'));
        var body = el('div', 'space-y-1.5 pt-2.5');
        var tags = el('div', 'flex flex-wrap gap-1');
        tags.appendChild(categoryTag(spot));
        tags.appendChild(tag(spot.mood.name, null, safeColor(spot.mood.pastel)));
        body.appendChild(tags);
        body.appendChild(el('p', 'text-base font-extrabold leading-tight', spot.name));
        body.appendChild(el('p', 'text-xs text-stone-600', metaLine(spot)));
        if (spot.hours) {
            var hours = el('p', 'flex items-center gap-1 text-[11px] font-semibold text-stone-500');
            hours.appendChild(icon('clock', 'h-3 w-3'));
            hours.appendChild(document.createTextNode(spot.hours));
            body.appendChild(hours);
        }
        if (spot.amenities.length || spot.wifi_mbps) body.appendChild(amenityTags(spot, 4));
        var actions = el('div', 'grid grid-cols-2 gap-2 pt-1.5');
        var details = el('a', 'btn btn-dark btn-sm !text-white', 'View spot');
        details.href = spot.url;
        var route = el('a', 'btn btn-soft btn-sm !text-ink');
        route.appendChild(icon('route', 'h-3.5 w-3.5'));
        route.appendChild(document.createTextNode('Directions'));
        route.href = spot.directions; route.target = '_blank'; route.rel = 'noopener';
        actions.appendChild(details); actions.appendChild(route);
        body.appendChild(actions);
        card.appendChild(body);
        return card;
    }

    // ---------------------------------------------------------------- list
    var results = document.getElementById('results');
    var emptyMsg = document.getElementById('empty');

    function listItem(spot) {
        var li = el('li');
        var btn = el('button', 'card flex w-full gap-3 p-3 text-left transition hover:shadow-md hover:[border-color:var(--ink)]');
        btn.type = 'button';
        btn.dataset.id = spot.id;
        btn.appendChild(thumb(spot, 'h-20 w-20 shrink-0 rounded-xl'));
        var info = el('div', 'min-w-0 flex-1 space-y-1');
        var top = el('div', 'flex items-center justify-between gap-2');
        top.appendChild(categoryTag(spot));
        if (distanceText(spot)) top.appendChild(el('span', 'whitespace-nowrap text-[11px] font-bold text-stone-600', distanceText(spot)));
        info.appendChild(top);
        info.appendChild(el('p', 'truncate text-sm font-extrabold', spot.name));
        var line = (spot.rating ? '★ ' + spot.rating + ' (' + spot.reviews + ')  ·  ' : '') +
                   spot.price.level + ' from ₱' + spot.price.starts_at;
        info.appendChild(el('p', 'text-[11px] text-stone-500', line));
        if (spot.amenities.length) {
            var icons = el('div', 'flex items-center gap-1.5 text-stone-500');
            spot.amenities.forEach(function (a) {
                var i = icon(a.icon, 'h-3.5 w-3.5');
                var holder = el('span'); holder.title = a.name; holder.appendChild(i);
                icons.appendChild(holder);
            });
            info.appendChild(icons);
        }
        if (!spot.is_approved) info.appendChild(tag('Pending approval', null, '#dc2626', '#fff'));
        btn.appendChild(info);
        btn.addEventListener('click', function () { focusSpot(spot.id, true); });
        btn.addEventListener('mouseenter', function () { highlight(spot.id, true); });
        btn.addEventListener('mouseleave', function () { highlight(spot.id, false); });
        li.appendChild(btn);
        return li;
    }

    function renderList() {
        results.textContent = '';
        spots.forEach(function (s) { results.appendChild(listItem(s)); });
        emptyMsg.classList.toggle('hidden', spots.length > 0);
        document.querySelectorAll('.js-count').forEach(function (n) { n.textContent = spots.length; });
        document.getElementById('result-hint').textContent = state.lat != null
            ? 'Nearest first' + (state.radius ? ' · within ' + state.radius + ' km' : '')
            : 'Top rated first';
    }

    // ---------------------------------------------------------------- markers
    function renderMarkers() {
        markersLayer.clearLayers();
        markers = {};
        spots.forEach(function (s) {
            var m = L.marker([s.lat, s.lng], {icon: pinIcon(s, false), title: s.name, riseOnHover: true});
            m.bindPopup(function () { return popupContent(s); }, {maxWidth: 280, className: 'at-popup'});
            m.on('popupopen', function () { highlight(s.id, true); });
            m.on('popupclose', function () { highlight(s.id, false); });
            m.addTo(markersLayer);
            markers[s.id] = m;
        });
    }

    function highlight(id, on) {
        var spot = spots.find(function (s) { return s.id === id; });
        var m = markers[id];
        if (spot && m) { m.setIcon(pinIcon(spot, on)); m.setZIndexOffset(on ? 1000 : 0); }
    }

    function focusSpot(id, collapseSheet) {
        var m = markers[id];
        if (!m) return;
        map.flyTo(m.getLatLng(), Math.max(map.getZoom(), 16), {duration: 0.6});
        m.openPopup();
        if (collapseSheet && window.innerWidth < 1024) setSheet(false);
    }

    // ---------------------------------------------------------------- origin (user / WMSU) + radius circle
    function drawOrigin() {
        originLayer.clearLayers();
        if (state.lat == null) return;
        var here = [state.lat, state.lng];
        L.circleMarker(here, {radius: 8, color: '#ffffff', weight: 3, fillColor: '#0ea5e9', fillOpacity: 1})
            .bindTooltip(state.originLabel || 'Search center').addTo(originLayer);
        if (state.radius) {
            L.circle(here, {radius: state.radius * 1000, color: '#f59332', weight: 2, fillColor: '#f59332', fillOpacity: 0.08, dashArray: '6 6'})
                .addTo(originLayer);
        }
    }

    function fitView() {
        var layers = [];
        originLayer.eachLayer(function (l) { layers.push(l); });
        markersLayer.eachLayer(function (l) { layers.push(l); });
        if (!layers.length) return;
        map.fitBounds(L.featureGroup(layers).getBounds(), {padding: [50, 50], maxZoom: 16});
    }

    // ---------------------------------------------------------------- fetching
    var controller = null;
    var loading = document.getElementById('loading');

    function queryString() {
        var p = new URLSearchParams();
        if (state.lat != null) { p.set('lat', state.lat.toFixed(6)); p.set('lng', state.lng.toFixed(6)); }
        if (state.lat != null && state.radius) p.set('radius', state.radius);
        if (state.category) p.set('category', state.category);
        state.amenities.forEach(function (a) { p.append('amenity', a); });
        if (state.mood) p.set('mood', state.mood);
        if (state.q) p.set('q', state.q);
        return p.toString();
    }

    function refresh(fit) {
        var qs = queryString();
        history.replaceState(null, '', location.pathname + (qs ? '?' + qs : ''));
        if (controller) controller.abort();
        controller = new AbortController();
        loading.classList.remove('hidden');
        fetch(API_URL + (qs ? '?' + qs : ''), {headers: {Accept: 'application/json'}, signal: controller.signal})
            .then(function (r) { return r.json().then(function (data) { return {ok: r.ok, data: data}; }); })
            .then(function (res) {
                if (!res.ok) throw new Error((res.data.errors || ['Request failed']).join(' '));
                spots = res.data.spots;
                renderAll(fit);
            })
            .catch(function (err) {
                if (err.name === 'AbortError') return;
                showStatus('Could not load spots: ' + err.message);
            })
            .finally(function () { loading.classList.add('hidden'); });
    }

    function renderAll(fit) {
        drawOrigin();
        renderMarkers();
        renderList();
        syncControls();
        if (fit) fitView();
    }

    // ---------------------------------------------------------------- controls (.chip from style.css)
    function setActive(btn, on) {
        btn.classList.toggle('is-active', on);
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    }

    function syncControls() {
        document.querySelectorAll('#radius-pills [data-radius]').forEach(function (b) {
            setActive(b, String(b.dataset.radius) === String(state.radius || ''));
            b.disabled = state.lat == null && b.dataset.radius !== '';
        });
        document.querySelectorAll('#category-pills [data-category]').forEach(function (b) {
            setActive(b, b.dataset.category === state.category);
        });
        document.querySelectorAll('#amenity-pills [data-amenity]').forEach(function (b) {
            setActive(b, state.amenities.indexOf(b.dataset.amenity) !== -1);
        });
    }

    document.getElementById('radius-pills').addEventListener('click', function (e) {
        var b = e.target.closest('[data-radius]');
        if (!b || b.disabled) return;
        state.radius = b.dataset.radius ? Number(b.dataset.radius) : null;
        refresh(true);
    });

    document.getElementById('category-pills').addEventListener('click', function (e) {
        var b = e.target.closest('[data-category]');
        if (!b) return;
        state.category = b.dataset.category;
        refresh(false);
    });

    document.getElementById('amenity-pills').addEventListener('click', function (e) {
        var b = e.target.closest('[data-amenity]');
        if (!b) return;
        var code = b.dataset.amenity;
        var i = state.amenities.indexOf(code);
        if (i === -1) state.amenities.push(code); else state.amenities.splice(i, 1);
        refresh(false);
    });

    document.getElementById('mood').addEventListener('change', function (e) {
        state.mood = e.target.value;
        refresh(false);
    });

    var searchTimer = null;
    document.getElementById('search').addEventListener('input', function (e) {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(function () { state.q = e.target.value.trim(); refresh(false); }, 300);
    });

    document.querySelectorAll('.area-chip').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var a = initial.areas[btn.dataset.area];
            if (a) map.flyTo([a.lat, a.lng], 15);
        });
    });

    // ---------------------------------------------------------------- "Find Spots Near Me"
    var statusBox = document.getElementById('locate-status');
    function showStatus(msg) {
        statusBox.textContent = msg;
        statusBox.classList.toggle('hidden', !msg);
    }

    function useOrigin(lat, lng, label) {
        state.lat = lat; state.lng = lng; state.originLabel = label;
        if (!state.radius) state.radius = 3;   // sensible default once we know where you are
        refresh(true);
    }

    document.getElementById('wmsu-btn').addEventListener('click', function () {
        showStatus('');
        useOrigin(initial.wmsu[0], initial.wmsu[1], 'WMSU');
    });

    document.getElementById('locate-btn').addEventListener('click', function () {
        if (!('geolocation' in navigator)) {
            showStatus('Your browser does not support location. Try "Near WMSU" instead.');
            return;
        }
        if (!window.isSecureContext) {
            showStatus('Location only works on https:// or on localhost / 127.0.0.1. Try "Near WMSU" instead.');
            return;
        }
        showStatus('Finding your location…');
        navigator.geolocation.getCurrentPosition(
            function (pos) {
                showStatus('Showing spots near you (accurate to about ' + Math.round(pos.coords.accuracy) + ' m).');
                useOrigin(pos.coords.latitude, pos.coords.longitude, 'You are here');
            },
            function (err) {
                var why = {1: 'Location permission was denied.', 2: 'Your location is unavailable right now.', 3: 'Finding your location took too long.'}[err.code] || 'Could not get your location.';
                showStatus(why + ' You can use "Near WMSU" instead.');
            },
            {enableHighAccuracy: true, timeout: 10000, maximumAge: 60000}
        );
    });

    // ---------------------------------------------------------------- mobile bottom sheet
    var sheet = document.getElementById('sheet');
    var sheetToggle = document.getElementById('sheet-toggle');
    function setSheet(open) {
        sheet.dataset.expanded = open ? 'true' : 'false';
        sheet.classList.toggle('max-h-[45%]', !open);
        sheet.classList.toggle('max-h-[85%]', open);
        sheetToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        document.getElementById('sheet-label').textContent = open ? 'Show map' : 'Show list';
    }
    sheetToggle.addEventListener('click', function () { setSheet(sheet.dataset.expanded !== 'true'); });

    // ---------------------------------------------------------------- go
    sizeExplorer();
    window.addEventListener('resize', sizeExplorer);
    // Re-measure whenever the map box itself changes size (window resize, sidebar <-> bottom-sheet switch,
    // header wrapping). Without this Leaflet keeps the old size and fitBounds() lands off-center.
    if ('ResizeObserver' in window) {
        new ResizeObserver(function () { map.invalidateSize(); }).observe(document.getElementById('map'));
    }
    window.addEventListener('load', function () { sizeExplorer(); fitView(); });
    renderAll(true);
})();

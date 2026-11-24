/*
 * Dashboard helpers (Admin + Spot Owner):
 *  - slide-in sidebar on phones / tablets
 *  - small static maps on approval cards: <div data-mini-map data-lat="" data-lng="" data-color="#hex">
 */
(function () {
    'use strict';

    // ---------------------------------------------------------------- sidebar (mobile)
    var sidebar = document.getElementById('dash-sidebar');
    var backdrop = document.querySelector('[data-sidebar-backdrop]');
    function setSidebar(open) {
        if (!sidebar) return;
        sidebar.classList.toggle('-translate-x-full', !open);
        backdrop.classList.toggle('hidden', !open);
        document.body.classList.toggle('overflow-hidden', open);
    }
    document.querySelectorAll('[data-sidebar-open]').forEach(function (b) { b.addEventListener('click', function () { setSidebar(true); }); });
    document.querySelectorAll('[data-sidebar-close]').forEach(function (b) { b.addEventListener('click', function () { setSidebar(false); }); });
    if (backdrop) backdrop.addEventListener('click', function () { setSidebar(false); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') setSidebar(false); });

    // ---------------------------------------------------------------- mini maps
    if (typeof L === 'undefined' || !window.ANDATAYO_MAP) return;
    document.querySelectorAll('[data-mini-map]').forEach(function (box) {
        var lat = parseFloat(box.dataset.lat), lng = parseFloat(box.dataset.lng);
        if (!isFinite(lat) || !isFinite(lng)) return;
        var color = /^#[0-9a-fA-F]{6}$/.test(box.dataset.color) ? box.dataset.color : '#f59332';
        var map = L.map(box, {
            zoomControl: false, dragging: false, scrollWheelZoom: false, doubleClickZoom: false,
            boxZoom: false, keyboard: false, touchZoom: false, attributionControl: true,
        }).setView([lat, lng], 16);
        L.tileLayer(window.ANDATAYO_MAP.tiles.url, window.ANDATAYO_MAP.tiles.options).addTo(map);
        L.circleMarker([lat, lng], {radius: 9, color: '#fff', weight: 3, fillColor: color, fillOpacity: 1}).addTo(map);
        // the card can finish its layout after the map starts: re-measure and keep the pin centred
        function recenter() { map.invalidateSize(); map.setView([lat, lng], 16, {animate: false}); }
        if ('ResizeObserver' in window) new ResizeObserver(recenter).observe(box);
        window.addEventListener('load', recenter);
    });
})();

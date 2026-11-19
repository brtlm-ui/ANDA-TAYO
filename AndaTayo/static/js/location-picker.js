/*
 * Location picker: click (or drag the pin) on a small Leaflet map to fill in the
 * "latitude" and "longitude" inputs. Typing coordinates moves the pin too.
 *
 * Used by:
 *   - Django Admin (core/admin.py -> SpotAdmin.Media)  -> inserted above the Latitude row
 *   - The public Submit/Edit spot form (templates/partials/_spot_form.html)
 *     -> rendered inside <div data-location-picker></div>
 *
 * Plain inline styles on purpose: the admin site does not load Tailwind.
 */
(function () {
    'use strict';

    var DEFAULT = window.ANDATAYO_MAP.defaultCenter;   // Zamboanga City (static/js/map-config.js)

    function init() {
        var latInput = document.getElementById('id_latitude');
        var lngInput = document.getElementById('id_longitude');
        if (!latInput || !lngInput || typeof L === 'undefined') return;

        // Where to put the map
        var host = document.querySelector('[data-location-picker]');
        if (!host) {
            var row = latInput.closest('.form-row') || latInput.parentElement;   // Django admin layout
            host = document.createElement('div');
            host.style.margin = '0 0 12px';
            row.parentNode.insertBefore(host, row);
        }

        var help = document.createElement('p');
        help.textContent = 'Click the map (or drag the pin) to set the location. ';
        help.style.cssText = 'margin:0 0 6px;font-size:12px;color:#666;';
        var locate = document.createElement('button');
        locate.type = 'button';
        locate.textContent = 'Use my current location';
        locate.style.cssText = 'margin-left:6px;padding:3px 10px;border-radius:999px;border:1px solid #bbb;background:#fff;cursor:pointer;font-size:12px;';
        help.appendChild(locate);

        var box = document.createElement('div');
        box.style.cssText = 'height:320px;max-width:720px;border-radius:12px;border:1px solid #ccc;';
        host.appendChild(help);
        host.appendChild(box);

        function current() {
            var lat = parseFloat(latInput.value), lng = parseFloat(lngInput.value);
            return isFinite(lat) && isFinite(lng) ? [lat, lng] : null;
        }

        var start = current();
        var map = L.map(box).setView(start || DEFAULT, start ? 17 : 14);
        L.tileLayer(window.ANDATAYO_MAP.tiles.url, window.ANDATAYO_MAP.tiles.options).addTo(map);

        var marker = null;
        function place(latlng, updateInputs) {
            if (!marker) {
                marker = L.marker(latlng, {draggable: true}).addTo(map);
                marker.on('dragend', function () { place(marker.getLatLng(), true); });
            } else {
                marker.setLatLng(latlng);
            }
            if (updateInputs) {
                var ll = L.latLng(latlng);
                latInput.value = ll.lat.toFixed(6);
                lngInput.value = ll.lng.toFixed(6);
                latInput.dispatchEvent(new Event('change'));
            }
        }
        if (start) place(start, false);

        map.on('click', function (e) { place(e.latlng, true); });

        function fromInputs() {
            var c = current();
            if (c) { place(c, false); map.panTo(c); }
        }
        latInput.addEventListener('input', fromInputs);
        lngInput.addEventListener('input', fromInputs);

        locate.addEventListener('click', function () {
            if (!navigator.geolocation) { alert('Your browser does not support location.'); return; }
            navigator.geolocation.getCurrentPosition(
                function (pos) {
                    var ll = [pos.coords.latitude, pos.coords.longitude];
                    place(ll, true);
                    map.setView(ll, 17);
                },
                function () { alert('Could not get your location. Click the map instead.'); },
                {enableHighAccuracy: true, timeout: 10000}
            );
        });

        // Maps inside collapsed / just-shown sections need a size refresh
        setTimeout(function () { map.invalidateSize(); }, 300);
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();

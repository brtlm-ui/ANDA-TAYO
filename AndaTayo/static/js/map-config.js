/*
 * Shared map settings for every Leaflet map on the site (map explorer, admin + form location picker).
 * Load this BEFORE map-explorer.js / location-picker.js.
 *
 * Tiles: OpenStreetMap's free volunteer servers. Their usage policy requires a Referer header -
 * requests without one get an "Access blocked" image. `referrerPolicy` below makes the browser send
 * our origin (e.g. http://127.0.0.1:8000/) with each tile request. Heavy production traffic should
 * switch `url` to a commercial / self-hosted tile provider.
 * Policy: https://operations.osmfoundation.org/policies/tiles/
 */
window.ANDATAYO_MAP = {
    tiles: {
        url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        options: {
            maxZoom: 19,
            referrerPolicy: 'strict-origin-when-cross-origin',
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        },
    },
    defaultCenter: [6.9214, 122.0790],   // Zamboanga City
};

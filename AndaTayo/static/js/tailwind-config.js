// Tailwind (Play CDN) theme for Anda Tayo. Loaded in base.html right after the Tailwind CDN script.
// Brand orange is taken from the logo (#F59332).
tailwind.config = {
    theme: {
        extend: {
            colors: {
                cream: '#f8efe3',
                sand: '#f2e6d6',
                brand: '#f59332',
                butter: '#ffe24a',
                ink: '#111111',
            },
            fontFamily: {
                sans: ['"Plus Jakarta Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
            },
        },
    },
};

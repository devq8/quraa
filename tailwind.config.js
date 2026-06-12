/**
 * Tailwind build for the Upwind/Shreethemes theme (Tailwind v3.4.1).
 *
 * The theme shipped a precompiled core/static/assets/css/tailwind.css that contains
 * the base layer + all custom components (.btn, .navbar, .nav-link, .form-input, ...).
 * That file is kept as-is. This config compiles ONLY the utility layer
 * (see tailwind/input.css) into core/static/assets/css/tailwind-utilities.css so that
 * any utility class used in a template is guaranteed to exist — without regenerating
 * (and losing) the theme's hand-tuned components.
 */
module.exports = {
  darkMode: 'class',
  content: [
    './**/templates/**/*.html',
    './core/static/assets/js/**/*.js',
  ],
  theme: {
    extend: {
      // Custom breakpoint used throughout the theme markup (e.g. lg_992:flex).
      screens: {
        lg_992: '992px',
      },
      fontFamily: {
        rubik: ['Rubik', 'sans-serif'],
      },
      // Semantic design tokens used by the search-results pagination markup.
      // Added so utilities like text-body / bg-neutral-secondary-medium /
      // border-default-medium / rounded-s-base actually compile.
      colors: {
        body: '#94a3b8',                       // idle text (slate-400)
        heading: '#111827',                    // hover text (gray-900)
        'fg-brand': '#99855B',                 // brand foreground (active page)
        'neutral-secondary-medium': '#ffffff', // default cell background
        'neutral-tertiary-medium': '#f9fafb',  // active/hover background (gray-50)
        'default-medium': '#e5e7eb',           // borders (gray-200)
      },
      borderRadius: {
        base: '0.375rem',
      },
    },
  },
  plugins: [],
}

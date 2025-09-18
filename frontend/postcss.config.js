/** @type {import('postcss-load-config').Config} */
module.exports = {
  plugins: {
    '@tailwindcss/postcss': {},  // ✅ correct plugin for v4
    autoprefixer: {},
  },
};

// Tailwind v4 uses a new PostCSS plugin package
module.exports = {
  plugins: {
    "@tailwindcss/postcss": {},  // ✅ not "tailwindcss"
    autoprefixer: {},
  },
};

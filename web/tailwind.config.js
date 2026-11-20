/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        slg: {
          bg: "#0f1117",
          panel: "#1a1d26",
          border: "#2b3040",
          accent: "#d97706",
          text: "#e2e8f0",
        }
      }
    },
  },
  plugins: [],
}

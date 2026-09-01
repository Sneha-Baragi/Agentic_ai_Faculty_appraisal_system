/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Source Sans 3", "Segoe UI", "sans-serif"],
        display: ["Source Serif 4", "Georgia", "serif"],
      },
      colors: {
        ink: "#1b2430",
        paper: "#f4f1ea",
        accent: "#2f5d50",
      },
    },
  },
  plugins: [],
};

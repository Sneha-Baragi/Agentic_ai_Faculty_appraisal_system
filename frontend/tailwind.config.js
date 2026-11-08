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
        ink: "#192522",
        paper: "#F4F7F6",
        surface: "#FFFFFF",
        subtle: "#F8FAF9",
        accent: "#245B4A",
        "accent-deep": "#194537",
        secondary: "#4F7C72",
        "text-secondary": "#53635E",
        muted: "#73817C",
        border: "#DCE5E1",
        divider: "#C7D4CE",
        success: "#23734D",
        pending: "#A76512",
        danger: "#B43A3A",
        neutral: "#5F6D68",
      },
    },
  },
  plugins: [],
};

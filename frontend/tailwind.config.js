/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        console: {
          bg: "#0B1220",      // sidebar / console navy
          bgSoft: "#141F33",  // sidebar hover
          line: "#233047",    // sidebar hairlines
        },
        paper: {
          DEFAULT: "#F3F5F2", // main content background (cool paper white)
          card: "#FFFFFF",
          line: "#DDE2DC",
        },
        ink: {
          DEFAULT: "#101820",
          soft: "#4B5A63",
          faint: "#8A968E",
        },
        freight: {
          DEFAULT: "#2F6F4E", // primary accent - freight green
          soft: "#E4EEE8",
          dark: "#1E4A33",
        },
        transit: {
          DEFAULT: "#C98A2C", // in-transit amber
          soft: "#F6E9D4",
        },
        alert: {
          DEFAULT: "#B23A2E", // returned / cancelled
          soft: "#F5DEDB",
        },
        scan: {
          DEFAULT: "#1E7F8C", // teal accent for linehaul/scan highlights
          soft: "#DCEEF0",
        },
      },
      boxShadow: {
        glow: "0 12px 32px -12px rgba(47,111,78,0.45)",
        "glow-alert": "0 12px 32px -12px rgba(178,58,46,0.4)",
      },
      fontFamily: {
        display: ["'IBM Plex Sans'", "system-ui", "sans-serif"],
        body: ["Inter", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
      },
    },
  },
  plugins: [],
};

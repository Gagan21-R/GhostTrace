/** Brutalist "evidence board" theme.
 * Paper background, ink-black 2-3px borders, hard offset shadows, a heavy display face and three loud accents:
 * acid yellow, flame (red-orange) and electric blue. The shared palette names used across components are remapped
 * here once, so every page picks up the theme without per-component changes. */

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    borderRadius: { none: "0", sm: "0", DEFAULT: "0", md: "2px", lg: "3px", xl: "4px", "2xl": "6px", full: "9999px" },
    extend: {
      fontFamily: {
        sans: ["'Space Grotesk'", "'Noto Sans Devanagari'", "'Noto Sans Kannada'", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"],
        display: ["'Archivo Black'", "'Noto Sans Devanagari'", "'Noto Sans Kannada'", "'Space Grotesk'", "Impact", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "Consolas", "monospace"],
      },
      colors: {
        paper: "#f3efe4",
        surface: "#fffdf6",
        acid: "#e4ff3a",
        flame: "#ff4f1f",
        volt: "#2b4bff",
        slate: { 50: "#f3efe4", 100: "#ebe6d8", 200: "#d6cfbd", 300: "#bcb4a0", 400: "#8f887a", 500: "#635e53", 600: "#4a463e",
                 700: "#36332d", 800: "#221f1b", 900: "#0d0c0a" },
        ink: { 950: "#0b0b0b", 900: "#0b0b0b", 800: "#1c1c1c", 700: "#3a3a3a" },
        accent: { 50: "#e7ebff", 100: "#c8d1ff", 500: "#2b4bff", 600: "#1d3bef", 700: "#1527a8" },
      },
      boxShadow: {
        card: "4px 4px 0 0 #0b0b0b",
        "brutal-sm": "2px 2px 0 0 #0b0b0b",
        brutal: "4px 4px 0 0 #0b0b0b",
        "brutal-lg": "7px 7px 0 0 #0b0b0b",
      },
      keyframes: {
        marquee: { from: { transform: "translateX(0)" }, to: { transform: "translateX(-50%)" } },
        wobble: { "0%,100%": { transform: "rotate(-2deg)" }, "50%": { transform: "rotate(2deg)" } },
        blink: { "0%,100%": { opacity: 1 }, "50%": { opacity: 0 } },
      },
      animation: { marquee: "marquee 28s linear infinite", "marquee-slow": "marquee 45s linear infinite", wobble: "wobble 3s ease-in-out infinite", blink: "blink 1s steps(1) infinite" },
    },
  },
  plugins: [],
};

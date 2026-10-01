/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ['"Instrument Sans"', "ui-sans-serif", "system-ui", "sans-serif"], display: ['"Fraunces"', "Georgia", "serif"], mono: ['"JetBrains Mono"', "ui-monospace", "monospace"] },
      colors: {
        paper: "rgb(var(--paper) / <alpha-value>)", card: "rgb(var(--card) / <alpha-value>)", ink: "rgb(var(--ink) / <alpha-value>)",
        mute: "rgb(var(--mute) / <alpha-value>)", line: "rgb(var(--line) / <alpha-value>)", brand: "rgb(var(--brand) / <alpha-value>)",
        ok: "rgb(var(--ok) / <alpha-value>)", warn: "rgb(var(--warn) / <alpha-value>)", bad: "rgb(var(--bad) / <alpha-value>)", info: "rgb(var(--info) / <alpha-value>)",
      },
      keyframes: { rise: { "0%": { opacity: 0, transform: "translateY(6px)" }, "100%": { opacity: 1, transform: "none" } }, pulseDot: { "0%,100%": { opacity: 0.3 }, "50%": { opacity: 1 } } },
      animation: { rise: "rise .28s ease-out both", dot: "pulseDot 1.2s ease-in-out infinite" },
    },
  },
  plugins: [],
};

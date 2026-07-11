import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef9ff",
          100: "#d8f1ff",
          200: "#b9e7ff",
          300: "#89daff",
          400: "#51c3ff",
          500: "#29a4ff",
          600: "#1186f7",
          700: "#0a6de3",
          800: "#0f58b8",
          900: "#134b91",
          950: "#112f58",
        },
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};
export default config;

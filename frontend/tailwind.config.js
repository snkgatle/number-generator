/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        // Single restrained accent used for primary actions, focus and active navigation.
        accent: {
          DEFAULT: '#6e79d6',
          hover: '#7f89e0',
          muted: 'rgba(110, 121, 214, 0.12)',
          border: 'rgba(110, 121, 214, 0.35)',
        },
        surface: {
          0: '#09090b',   // app background
          1: '#0f0f12',   // sidebar / top bar
          2: '#131316',   // cards
          3: '#1a1a1e',   // inset / hover
        },
        line: {
          DEFAULT: '#232328',
          strong: '#2e2e34',
        },
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
    },
  },
  plugins: [],
}

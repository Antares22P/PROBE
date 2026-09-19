/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Cascadia Code', 'monospace'],
      },
      colors: {
        probe: {
          bg: '#0a0a0f',
          surface: '#111118',
          border: '#1e1e2e',
          accent: '#6366f1',
          'accent-dim': '#4f52c4',
          muted: '#6b7280',
          text: '#e2e8f0',
          'text-dim': '#94a3b8',
        }
      }
    },
  },
  plugins: [],
}

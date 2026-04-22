/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        twitch: {
          purple: '#9146ff',
          dark:   '#0e0e10',
          card:   '#1f1f23',
          border: '#2f2f35',
          muted:  '#adadb8',
        },
      },
    },
  },
  plugins: [],
}

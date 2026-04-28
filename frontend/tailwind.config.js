/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
      },
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

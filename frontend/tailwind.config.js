/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'primary-dark': '#061E29',
        primary: '#1D546D',
        secondary: '#5F9598',
        'bg-light': '#F3F4F4',
      },
    },
  },
  plugins: [],
}

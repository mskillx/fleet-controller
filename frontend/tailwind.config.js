/** @type {import('tailwindcss').Config} */
const themes = {
  blue: require('./themes/blue'),
  orange: require('./themes/orange'),
}

const theme = themes[process.env.VITE_THEME] ?? themes.blue

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: theme,
    },
  },
  plugins: [],
}

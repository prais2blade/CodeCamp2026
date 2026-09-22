module.exports = {
  content: [
    './templates/**/*.html',
    './website/templates/**/*.html',
    './**/templates/**/*.html',
    './website/**/*.js'
  ],

  theme: {
    extend: {
      colors: {
        primary: "#7A32FF",        // Neon Purple
        primaryDark: "#3B0CA6",    // Deep Purple Glow
        primaryLight: "#B084FF",   // Soft highlight
        secondary: "#00A86B",
        dark: "#0A061A",
        muted: "#F5F7FA",
        softWhite: "#F7F4FF",
      },

      backgroundImage: {
        'hero-gradient': "linear-gradient(135deg, #3B0CA6, #7A32FF)",
      },

      boxShadow: {
        glow: "0 0 18px rgba(122, 50, 255, 0.6)",
      },

      keyframes: {
        fadeIn: {
          '0%': { opacity: 0, transform: 'translateY(20px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' }
        },

        /** 🔥 Glow Pulse */
        'glow-pulse': {
          '0%, 100%': {
            boxShadow:
              '0 0 20px rgba(122, 50, 255, 0.6), 0 0 35px rgba(176, 132, 255, 0.5)',
          },
          '50%': {
            boxShadow:
              '0 0 35px rgba(122, 50, 255, 0.9), 0 0 60px rgba(176, 132, 255, 0.7)',
          },
        },

        /** ✨ Shimmer (light sweep) */
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },

        /** ⚡ Moving Gradient */
        'gradient-move': {
          '0%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
      },

      animation: {
        fadeIn: 'fadeIn 1s ease-out forwards',

        /** Glow Pulse */
        'glow-pulse': 'glow-pulse 2.5s ease-in-out infinite',

        /** Shimmer */
        shimmer: 'shimmer 2s linear infinite',

        /** Moving Gradient */
        'gradient-move': 'gradient-move 6s ease infinite',
      },
    },
  },

  plugins: [],
};

import { createTheme, responsiveFontSizes } from '@mui/material/styles';

// TalentPilot Brand Colors — warm, sophisticated palette
const palette = {
  // Mauve Shadow — primary actions, header
  mauveShadow: '#6B4D57',
  // Smoky Rose — secondary, text secondary, accents
  smokyRose: '#896A67',
  // Almond Silk — hover states, subtle backgrounds
  almondSilk: '#DDC8C4',
  // Mint Cream — page background
  mintCream: '#EFF9F0',
  // Coffee Bean — primary text
  coffeeBean: '#13070C',
};

const brandColors = {
  primary: {
    main: palette.mauveShadow,
    light: palette.smokyRose,
    dark: '#4D3740',
    contrastText: '#ffffff',
  },
  secondary: {
    main: palette.smokyRose,
    light: palette.almondSilk,
    dark: '#6B5A57',
    contrastText: '#ffffff',
  },
  success: {
    main: '#5B8C5A',
    light: '#7AAA78',
    dark: '#3D6B3C',
    contrastText: '#ffffff',
  },
  warning: {
    main: '#C49B4A',
    light: '#D4B36E',
    dark: '#9B7A30',
    contrastText: '#ffffff',
  },
  error: {
    main: '#C4544A',
    light: '#D4786E',
    dark: '#9B3A30',
    contrastText: '#ffffff',
  },
  info: {
    main: '#6B7B8D',
    light: '#8B9BAB',
    dark: '#4D5B6B',
    contrastText: '#ffffff',
  },
  background: {
    default: palette.mintCream,
    paper: '#fdfbf9',
  },
  text: {
    primary: palette.coffeeBean,
    secondary: palette.smokyRose,
  },
  divider: '#e8e0dc',
};

let theme = createTheme({
  palette: brandColors,
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: { fontWeight: 700, letterSpacing: '-0.02em' },
    h2: { fontWeight: 600, letterSpacing: '-0.01em' },
    h3: { fontWeight: 600 },
    h4: { fontWeight: 600 },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600, letterSpacing: '-0.01em' },
    subtitle1: { fontWeight: 500 },
    button: { textTransform: 'none', fontWeight: 600 },
  },
  shape: { borderRadius: 10 },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          padding: '8px 20px',
          transition: 'all 0.2s ease',
        },
        contained: {
          boxShadow: 'none',
          '&:hover': { boxShadow: '0 2px 8px rgba(107,77,87,0.25)' },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 14,
          backgroundImage: 'none',
        },
        elevation1: {
          boxShadow: '0 1px 3px rgba(19,7,12,0.06), 0 1px 2px rgba(19,7,12,0.04)',
        },
        elevation2: {
          boxShadow: '0 2px 8px rgba(19,7,12,0.08)',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundImage: `linear-gradient(135deg, ${palette.mauveShadow}, #5A3E48)`,
          boxShadow: '0 2px 12px rgba(19,7,12,0.12)',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { borderRadius: 8 },
        outlined: { borderColor: brandColors.divider },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          transition: 'box-shadow 0.2s ease, transform 0.15s ease',
          '&:hover': { transform: 'translateY(-2px)' },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 12,
            backgroundColor: '#fdfbf9',
            '&:hover .MuiOutlinedInput-notchedOutline': {
              borderColor: palette.smokyRose,
            },
          },
        },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: {
          borderRadius: 6,
          backgroundColor: '#e8e0dc',
        },
      },
    },
    MuiAvatar: {
      styleOverrides: {
        root: {
          fontWeight: 600,
        },
      },
    },
  },
});

// Make fonts responsive
theme = responsiveFontSizes(theme);

export default theme;

import React, { createContext, useContext, useState, useEffect } from 'react';

// 主题定义
const themes = {
  light: {
    name: '浅色',
    colors: {
      bg: '#ffffff', bgSecondary: '#f1f5f9', text: '#1e293b',
      textSecondary: '#64748b', primary: '#3b82f6', accent: '#06b6d4',
      border: '#e2e8f0', cardBg: '#f8fafc', success: '#10b981',
      warning: '#f59e0b', error: '#ef4444',
    }
  },
  dark: {
    name: '深色',
    colors: {
      bg: '#0f172a', bgSecondary: '#1e293b', text: '#e2e8f0',
      textSecondary: '#94a3b8', primary: '#60a5fa', accent: '#22d3ee',
      border: '#334155', cardBg: '#1e293b', success: '#34d399',
      warning: '#fbbf24', error: '#f87171',
    }
  },
  ocean: {
    name: '海洋',
    colors: {
      bg: '#f0f9ff', bgSecondary: '#e0f2fe', text: '#0c4a6e',
      textSecondary: '#0369a1', primary: '#0284c7', accent: '#06b6d4',
      border: '#bae6fd', cardBg: '#f0f9ff', success: '#059669',
      warning: '#d97706', error: '#dc2626',
    }
  }
};

const ThemeContext = createContext();

export function ThemeProvider({ children }) {
  const [themeName, setThemeName] = useState(() => localStorage.getItem('theme') || 'light');

  useEffect(() => {
    const root = document.documentElement;
    const theme = themes[themeName].colors;
    Object.entries(theme).forEach(([key, val]) => {
      root.style.setProperty(`--color-${key}`, val);
    });
    localStorage.setItem('theme', themeName);
  }, [themeName]);

  return (
    <ThemeContext.Provider value={{ themeName, setThemeName, themes, current: themes[themeName] }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);

// ── 组件 ──

function ThemeSwitcher() {
  const { themeName, setThemeName, themes: allThemes } = useTheme();
  return (
    <div style={s.switcher}>
      {Object.entries(allThemes).map(([key, t]) => (
        <button key={key} onClick={() => setThemeName(key)}
          style={{...s.themeBtn, background: themeName === key ? 'var(--color-primary)' : 'var(--color-bgSecondary)',
            color: themeName === key ? 'white' : 'var(--color-text)' }}>
          {t.name}
        </button>
      ))}
    </div>
  );
}

function Card({ title, children, variant = 'default' }) {
  const colors = {
    default: 'var(--color-cardBg)',
    primary: 'var(--color-primary)',
    success: 'var(--color-success)',
    warning: 'var(--color-warning)',
    error: 'var(--color-error)',
  };
  return (
    <div style={{...s.card, background: colors[variant], color: variant !== 'default' ? 'white' : 'var(--color-text)' }}>
      <h3 style={s.cardTitle}>{title}</h3>
      {children}
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <div style={s.container}>
        <header style={s.header}>
          <h1>🎨 主题系统演示</h1>
          <ThemeSwitcher />
        </header>

        <div style={s.grid}>
          <Card title="默认卡片">
            <p>使用 CSS 变量实现主题切换，所有颜色自动适配。</p>
          </Card>
          <Card title="主要操作" variant="primary">
            <p>主要按钮和强调色跟随主题变化。</p>
          </Card>
          <Card title="成功状态" variant="success">
            <p>操作成功的反馈信息。</p>
          </Card>
          <Card title="警告提示" variant="warning">
            <p>需要注意的警告信息。</p>
          </Card>
          <Card title="错误信息" variant="error">
            <p>错误和异常状态的展示。</p>
          </Card>
        </div>

        <div style={s.demo}>
          <h2>CSS 变量示例</h2>
          <div style={s.colorGrid}>
            {['bg', 'bgSecondary', 'text', 'textSecondary', 'primary', 'accent', 'success', 'warning', 'error'].map(c => (
              <div key={c} style={{...s.colorSwatch, background: `var(--color-${c})`}}>
                <span style={{color: c.includes('bg') ? 'var(--color-text)' : 'white'}}>{c}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </ThemeProvider>
  );
}

const s = {
  container: { minHeight: '100vh', background: 'var(--color-bg)', color: 'var(--color-text)', fontFamily: 'system-ui', padding: 24, transition: 'all 0.3s' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 },
  switcher: { display: 'flex', gap: 8 },
  themeBtn: { padding: '8px 16px', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 14, transition: 'all 0.2s' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16, marginBottom: 32 },
  card: { padding: 20, borderRadius: 12, transition: 'all 0.3s' },
  cardTitle: { marginBottom: 8 },
  demo: { background: 'var(--color-bgSecondary)', padding: 24, borderRadius: 12 },
  colorGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 8, marginTop: 16 },
  colorSwatch: { height: 80, borderRadius: 8, display: 'flex', alignItems: 'flex-end', padding: 8, fontSize: 12, fontWeight: 600 },
};

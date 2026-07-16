import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

function FadeIn({ children }) {
  return (
    <motion.div initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }} transition={{ duration: 0.6 }}>
      {children}
    </motion.div>
  );
}

function PulseButton() {
  return (
    <motion.button whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}
      style={{ ...s.btn, background: '#3b82f6' }}>
      点我!
    </motion.button>
  );
}

function AnimatedCard({ title, children, index }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -50 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.15, duration: 0.5 }}
      whileHover={{ scale: 1.03, boxShadow: '0 10px 30px rgba(0,0,0,0.15)' }}
      style={s.card}>
      <h3>{title}</h3>
      {children}
    </motion.div>
  );
}

function ToggleList() {
  const [items, setItems] = useState([1, 2, 3]);
  return (
    <div>
      <button style={s.btn} onClick={() => setItems([...items, items.length + 1])}>添加</button>
      <button style={{...s.btn, background: '#ef4444'}} onClick={() => setItems(items.slice(0, -1))}>移除</button>
      <div style={{ marginTop: 16 }}>
        <AnimatePresence>
          {items.map(i => (
            <motion.div key={i} initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.3 }}
              style={{ ...s.card, marginBottom: 8, overflow: 'hidden' }}>
              列表项 #{i}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

function DragDemo() {
  return (
    <div style={{ height: 200, position: 'relative', background: '#f1f5f9', borderRadius: 12, overflow: 'hidden' }}>
      <motion.div drag dragConstraints={{ left: 0, right: 300, top: 0, bottom: 100 }}
        whileDrag={{ scale: 1.1 }} style={{ width: 80, height: 80, background: '#8b5cf6', borderRadius: 16,
          position: 'absolute', cursor: 'grab', display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'white', fontWeight: 700 }}>
        拖我
      </motion.div>
    </div>
  );
}

export default function App() {
  return (
    <div style={s.container}>
      <motion.h1 initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }} style={{ textAlign: 'center', color: '#1e293b' }}>
        ✨ 动画演示
      </motion.h1>

      <FadeIn>
        <div style={s.section}>
          <h2>渐变卡片</h2>
          <div style={s.grid}>
            {['React', 'Framer Motion', 'CSS Animation', 'Gesture'].map((title, i) => (
              <AnimatedCard key={title} title={title} index={i}>
                <p style={{ color: '#64748b' }}>流畅的入场动画与悬浮效果</p>
              </AnimatedCard>
            ))}
          </div>
        </div>
      </FadeIn>

      <FadeIn>
        <div style={s.section}>
          <h2>按钮交互</h2>
          <PulseButton />
          <motion.div style={{ width: 60, height: 60, borderRadius: 30, background: '#10b981', margin: '16px 0' }}
            animate={{ rotate: [0, 10, -10, 0] }} transition={{ repeat: Infinity, duration: 0.5 }} />
        </div>
      </FadeIn>

      <FadeIn>
        <div style={s.section}>
          <h2>列表动画 (AnimatePresence)</h2>
          <ToggleList />
        </div>
      </FadeIn>

      <FadeIn>
        <div style={s.section}>
          <h2>拖拽手势</h2>
          <DragDemo />
        </div>
      </FadeIn>
    </div>
  );
}

const s = {
  container: { maxWidth: 800, margin: '0 auto', padding: 24, fontFamily: 'system-ui', background: '#f8fafc', minHeight: '100vh' },
  section: { marginBottom: 40 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 },
  card: { background: 'white', padding: 20, borderRadius: 12, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' },
  btn: { padding: '10px 20px', border: 'none', borderRadius: 8, color: 'white', fontWeight: 600, cursor: 'pointer', marginRight: 8, fontSize: 14 },
};

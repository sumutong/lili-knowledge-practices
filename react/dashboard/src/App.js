import React, { useState, useEffect } from 'react';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const salesData = [
  { month: '1月', sales: 4000, orders: 240 },
  { month: '2月', sales: 3000, orders: 198 },
  { month: '3月', sales: 5000, orders: 305 },
  { month: '4月', sales: 4780, orders: 289 },
  { month: '5月', sales: 5890, orders: 350 },
  { month: '6月', sales: 6390, orders: 412 },
];

const pieData = [
  { name: '电子产品', value: 400 },
  { name: '服装', value: 300 },
  { name: '食品', value: 200 },
  { name: '图书', value: 100 },
];
const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444'];

function StatCard({ title, value, change, icon }) {
  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <span style={styles.cardIcon}>{icon}</span>
        <span style={styles.cardChange}>{change}</span>
      </div>
      <div style={styles.cardValue}>{value}</div>
      <div style={styles.cardTitle}>{title}</div>
    </div>
  );
}

export default function Dashboard() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1>📊 立里数据仪表盘</h1>
        <span>{time.toLocaleString('zh-CN')}</span>
      </header>

      <div style={styles.statsGrid}>
        <StatCard icon="💰" title="总销售额" value="¥128,430" change="+12.5%" />
        <StatCard icon="📦" title="总订单" value="1,794" change="+8.2%" />
        <StatCard icon="👥" title="活跃用户" value="3,256" change="+23.1%" />
        <StatCard icon="📈" title="转化率" value="4.8%" change="+1.2%" />
      </div>

      <div style={styles.chartsGrid}>
        <div style={styles.chartCard}>
          <h3>月度销售趋势</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={salesData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="sales" stroke="#3b82f6" strokeWidth={2} name="销售额" />
              <Line type="monotone" dataKey="orders" stroke="#10b981" strokeWidth={2} name="订单数" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div style={styles.chartCard}>
          <h3>品类分布</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" outerRadius={100} dataKey="value" label>
                {pieData.map((_, idx) => <Cell key={idx} fill={COLORS[idx % COLORS.length]} />)}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div style={{...styles.chartCard, gridColumn: 'span 2'}}>
          <h3>月度对比</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={salesData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="sales" fill="#3b82f6" name="销售额" />
              <Bar dataKey="orders" fill="#10b981" name="订单数" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: { maxWidth: 1400, margin: '0 auto', padding: 24, fontFamily: 'system-ui', background: '#f1f5f9', minHeight: '100vh' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24, color: '#1e293b' },
  statsGrid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 },
  card: { background: 'white', padding: 20, borderRadius: 12, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' },
  cardHeader: { display: 'flex', justifyContent: 'space-between', marginBottom: 8 },
  cardIcon: { fontSize: 24 },
  cardChange: { color: '#10b981', fontWeight: 600 },
  cardValue: { fontSize: 28, fontWeight: 700, color: '#1e293b', marginBottom: 4 },
  cardTitle: { color: '#64748b', fontSize: 14 },
  chartsGrid: { display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 },
  chartCard: { background: 'white', padding: 20, borderRadius: 12, boxShadow: '0 1px 3px rgba(0,0,0,0.1)' },
};

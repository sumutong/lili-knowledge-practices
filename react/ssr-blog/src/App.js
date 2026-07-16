import React from 'react';
import { BrowserRouter, Routes, Route, Link, useParams } from 'react-router-dom';

// 模拟博客数据
const posts = [
  { id: 1, title: 'React 19 新特性详解', author: '立里', date: '2026-07-10', excerpt: 'React 19带来了全新的并发特性...', content: 'React 19 是一个重大更新，引入了 Server Components、Actions、新的 Hooks 等重要特性...', tags: ['React', '前端'] },
  { id: 2, title: 'Next.js 服务端渲染实战', author: '立里', date: '2026-07-08', excerpt: 'SSR提升首屏加载速度...', content: '服务端渲染（SSR）可以显著提升页面的首屏加载速度和SEO表现...', tags: ['Next.js', 'SSR'] },
  { id: 3, title: 'Tailwind CSS 设计系统', author: '立里', date: '2026-07-05', excerpt: '构建可维护的设计系统...', content: 'Tailwind CSS 提供了 utility-first 的方式来构建一致的设计系统...', tags: ['CSS', '设计'] },
  { id: 4, title: 'TypeScript高级类型体操', author: '立里', date: '2026-07-01', excerpt: '深入理解TS类型系统...', content: 'TypeScript的类型系统非常强大，条件类型、映射类型、模板字面量类型...', tags: ['TypeScript'] },
];

const style = `
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: system-ui; background: #f8fafc; color: #1e293b; }
  .header { background: linear-gradient(135deg,#1e293b,#334155); color: white; padding: 2rem; text-align: center; }
  .nav { background: white; padding: 1rem 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); position: sticky; top:0; }
  .nav a { color: #64748b; text-decoration: none; margin-right: 1.5rem; }
  .nav a:hover { color: #3b82f6; }
  .container { max-width: 800px; margin: 2rem auto; padding: 0 1rem; }
  .post-card { background: white; border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  .post-card h2 { color: #1e40af; margin-bottom: 0.5rem; }
  .post-card h2 a { color: inherit; text-decoration: none; }
  .post-card .meta { color: #94a3b8; font-size: 0.875rem; margin-bottom: 0.5rem; }
  .post-card .tags { margin-top: 0.5rem; }
  .post-card .tag { display: inline-block; background: #dbeafe; color: #1e40af; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-right: 4px; }
  .article { background: white; border-radius: 12px; padding: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  .article h1 { color: #1e40af; margin-bottom: 1rem; }
  .article .content { line-height: 1.8; font-size: 1.05rem; }
  .back { color: #3b82f6; text-decoration: none; display: inline-block; margin-bottom: 1rem; }
  .footer { text-align: center; color: #94a3b8; padding: 2rem; }
`;

function Home() {
  return (
    <div>
      <style>{style}</style>
      <div className="header"><h1>📝 立里技术博客</h1><p>SSR 服务端渲染实战</p></div>
      <div className="nav"><a href="/">首页</a><a href="/">React</a><a href="/">前端</a><a href="/">全栈</a></div>
      <div className="container">
        {posts.map(post => (
          <div className="post-card" key={post.id}>
            <h2><Link to={`/post/${post.id}`}>{post.title}</Link></h2>
            <div className="meta">{post.author} · {post.date}</div>
            <p>{post.excerpt}</p>
            <div className="tags">{post.tags.map(t => <span className="tag" key={t}>{t}</span>)}</div>
          </div>
        ))}
      </div>
      <div className="footer">Powered by React Router · SSR 实战</div>
    </div>
  );
}

function Post() {
  const { id } = useParams();
  const post = posts.find(p => p.id === parseInt(id));

  if (!post) return <div className="container"><h2>文章不存在</h2></div>;

  return (
    <div>
      <style>{style}</style>
      <div className="header"><h1>📝 立里技术博客</h1></div>
      <div className="container">
        <Link to="/" className="back">← 返回首页</Link>
        <div className="article">
          <h1>{post.title}</h1>
          <div className="meta" style={{marginBottom: '1.5rem'}}>{post.author} · {post.date}</div>
          <div className="content">{post.content}</div>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/post/:id" element={<Post />} />
      </Routes>
    </BrowserRouter>
  );
}

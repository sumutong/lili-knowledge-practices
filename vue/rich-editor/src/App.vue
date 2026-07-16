<template>
  <div class="editor-app">
    <header>
      <h1>✍️ 富文本编辑器实战</h1>
      <p>基于 TipTap 的所见即所得编辑器</p>
    </header>
    <div class="editor-wrapper">
      <div class="toolbar">
        <button @click="editor.chain().focus().toggleBold().run()" :class="{ active: editor.isActive('bold') }"><b>B</b></button>
        <button @click="editor.chain().focus().toggleItalic().run()" :class="{ active: editor.isActive('italic') }"><i>I</i></button>
        <button @click="editor.chain().focus().toggleStrike().run()" :class="{ active: editor.isActive('strike') }"><s>S</s></button>
        <button @click="editor.chain().focus().toggleHeading({ level: 2 }).run()" :class="{ active: editor.isActive('heading', { level: 2 }) }">H2</button>
        <button @click="editor.chain().focus().toggleBulletList().run()" :class="{ active: editor.isActive('bulletList') }">列表</button>
        <button @click="editor.chain().focus().toggleBlockquote().run()" :class="{ active: editor.isActive('blockquote') }">引用</button>
        <button @click="editor.chain().focus().toggleCodeBlock().run()" :class="{ active: editor.isActive('codeBlock') }">代码</button>
      </div>
      <editor-content :editor="editor" class="editor-content" />
    </div>
    <div class="output-panel">
      <h3>📄 HTML 输出</h3>
      <pre>{{ output }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'

const output = ref('')

const editor = useEditor({
  content: '<h2>欢迎使用富文本编辑器</h2><p>这是一段 <strong>加粗</strong> 和 <em>斜体</em> 文字。</p><ul><li>支持列表</li><li>支持引用</li></ul>',
  extensions: [StarterKit],
  onUpdate: ({ editor: ed }) => { output.value = ed.getHTML() }
})

onBeforeUnmount(() => editor.value?.destroy())
</script>

<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui,sans-serif;background:#f8f9fa}
.editor-app{max-width:800px;margin:0 auto;padding:24px}
header{text-align:center;padding:24px 0}
header h1{color:#333}header p{color:#666;margin-top:6px}
.editor-wrapper{border:1px solid #ddd;border-radius:8px;overflow:hidden;background:#fff}
.toolbar{display:flex;gap:4px;padding:10px;border-bottom:1px solid #eee;flex-wrap:wrap}
.toolbar button{width:32px;height:32px;border:1px solid #ddd;background:#fff;border-radius:4px;cursor:pointer;font-size:14px;display:flex;align-items:center;justify-content:center}
.toolbar button.active{background:#42b883;color:#fff;border-color:#42b883}
.editor-content{padding:20px;min-height:300px}
.editor-content :focus{outline:none}
.output-panel{margin-top:24px}
.output-panel h3{margin-bottom:10px}
.output-panel pre{background:#2d2d2d;color:#f8f8f2;padding:16px;border-radius:8px;font-size:13px;overflow-x:auto;max-height:200px}
</style>

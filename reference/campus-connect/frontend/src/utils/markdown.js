// Tiny, dependency-free Markdown renderer for the AI assistant's replies.
// The assistant only ever returns a couple of short sentences with the
// occasional **bold** club name, so we deliberately support a small, safe
// subset rather than pulling in a full parser. HTML is escaped first, so
// nothing the model returns can inject markup - only our own <strong>/<em>/
// <br> tags reach the DOM.

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function renderMarkdown(raw) {
  if (!raw) return ''

  let html = escapeHtml(String(raw).trim())

  // **bold** and __bold__
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/__([^_]+)__/g, '<strong>$1</strong>')

  // *italic* and _italic_ (after bold so the ** pairs are already consumed)
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  html = html.replace(/_([^_]+)_/g, '<em>$1</em>')

  // `inline code`
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')

  // paragraphs (blank line) and soft line breaks
  const paragraphs = html.split(/\n{2,}/).map(function wrap(block) {
    return '<p>' + block.replace(/\n/g, '<br>') + '</p>'
  })

  return paragraphs.join('')
}

// Plain-text version for the speech narrator - strips the markdown markers so
// the synthesizer does not read "asterisk asterisk" out loud.
export function stripMarkdown(raw) {
  if (!raw) return ''
  return String(raw)
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/_([^_]+)_/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\s+/g, ' ')
    .trim()
}

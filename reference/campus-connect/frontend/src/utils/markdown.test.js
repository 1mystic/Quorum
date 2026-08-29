import { describe, test, expect } from 'vitest'
import { renderMarkdown, stripMarkdown } from './markdown'

describe('renderMarkdown', () => {
  test('renders bold and wraps in a paragraph', () => {
    expect(renderMarkdown('try **Robotics Club** today')).toBe(
      '<p>try <strong>Robotics Club</strong> today</p>'
    )
  })

  test('renders italics', () => {
    expect(renderMarkdown('a *warm* welcome')).toBe('<p>a <em>warm</em> welcome</p>')
  })

  test('escapes raw HTML so nothing can inject markup', () => {
    expect(renderMarkdown('<script>alert(1)</script>')).not.toContain('<script>')
  })

  test('splits blank lines into separate paragraphs', () => {
    expect(renderMarkdown('one\n\ntwo')).toBe('<p>one</p><p>two</p>')
  })

  test('returns an empty string for empty input', () => {
    expect(renderMarkdown('')).toBe('')
  })
})

describe('stripMarkdown', () => {
  test('removes bold and italic markers for the narrator', () => {
    expect(stripMarkdown('try **Robotics** and *Coding*')).toBe('try Robotics and Coding')
  })
})

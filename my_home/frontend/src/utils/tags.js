const PALETTE = ['blue', 'teal', 'green', 'orange', 'deep-purple', 'pink', 'indigo', 'cyan', 'brown']

export const stripTag = value => String(value || '').trim().replace(/^#+/, '')

export const normalizeTag = value => {
  const text = stripTag(value)
  return text ? `#${text}` : ''
}

export const tagColor = value => {
  const text = stripTag(value).toLowerCase()
  let hash = 0
  for (let index = 0; index < text.length; index += 1) hash = ((hash << 5) - hash) + text.charCodeAt(index)
  return PALETTE[Math.abs(hash) % PALETTE.length]
}

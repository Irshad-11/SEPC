import { useState } from 'react'
import gold from '../assets/medal-gold.svg'
import silver from '../assets/medal-silver.svg'
import bronze from '../assets/medal-bronze.svg'
import devBadge from '../assets/dev-badge.svg'

const MEDALS = { 1: gold, 2: silver, 3: bronze }
const PLACEHOLDER =
  'data:image/svg+xml,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40"><rect width="40" height="40" fill="#E9E5D8"/>' +
      '<circle cx="20" cy="15.5" r="7" fill="#9A7E3B"/><path d="M6 38c1.5-8 7-12 14-12s12.5 4 14 12z" fill="#9A7E3B"/></svg>',
  )

// photo + medal frame (1st/2nd/3rd) + developer badge
export default function Avatar({ src, size = 28, medal = 0, dev = false, reveal = false }) {
  const [broken, setBroken] = useState(false)
  const frame = size / 0.62
  return (
    <div className={`av${reveal ? ' reveal' : ''}`} style={{ width: size, height: size }}>
      <img className={`photo${!src || broken ? ' ph' : ''}`} src={!src || broken ? PLACEHOLDER : src} alt="" loading="lazy" onError={() => setBroken(true)} referrerPolicy="no-referrer" />
      {medal > 0 && (
        <img className="frame" src={MEDALS[medal]} alt={`#${medal}`}
          style={{ width: frame, height: frame * 1.04, left: (size - frame) / 2, top: (size - frame * 1.04) / 2 }} />
      )}
      {dev && <img className="dev" src={devBadge} alt="Developer" title="SEPC Developer" style={{ width: size * 0.46, height: size * 0.46 }} />}
    </div>
  )
}

export { devBadge }

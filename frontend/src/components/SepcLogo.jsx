// SEPC mark: </> drawn with animated strokes
export default function SepcLogo({ size = 26 }) {
  return (
    <svg className="sepc-logo" width={size} height={size} viewBox="0 0 32 32" aria-label="SEPC">
      <rect x="1" y="1" width="30" height="30" rx="6" fill="none" stroke="#9A7E3B" strokeWidth="1.5" />
      <path d="M11 10 L5.5 16 L11 22" pathLength="1" fill="none" stroke="#C9A85C" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M21 10 L26.5 16 L21 22" pathLength="1" fill="none" stroke="#C9A85C" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M18 8.5 L14 23.5" pathLength="1" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  )
}

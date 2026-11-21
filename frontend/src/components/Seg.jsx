// small segmented control: options = [{key, label}]
export default function Seg({ options, value, onChange }) {
  return (
    <div className="seg" role="tablist">
      {options.map((o) => (
        <button key={o.key} className={o.key === value ? 'on' : ''} onClick={() => onChange(o.key)} role="tab" aria-selected={o.key === value}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

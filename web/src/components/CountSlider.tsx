import './Forms.css'

interface CountSliderProps {
  label: string
  ariaLabel: string
  min: number
  max: number
  value: number
  onChange: (value: number) => void
}

export function CountSlider({ label, ariaLabel, min, max, value, onChange }: CountSliderProps) {
  return (
    <div className="form-field">
      <h6>{label}</h6>
      <div className="form-count">
        <input
          type="range"
          min={min}
          max={max}
          step={1}
          value={value}
          aria-label={ariaLabel}
          onChange={(event) => onChange(Number(event.target.value))}
        />
        <span className="tabular form-count-value">{value}</span>
      </div>
    </div>
  )
}

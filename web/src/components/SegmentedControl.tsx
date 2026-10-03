import './Forms.css'

interface SegmentedControlProps<T extends string> {
  // Prefix it per form (`fc-scope`, `qz-scope`): both config forms stay mounted, and
  // radios sharing a name page-wide would share one selection.
  name: string
  label: string
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
}

export function SegmentedControl<T extends string>({
  name,
  label,
  value,
  options,
  onChange,
}: SegmentedControlProps<T>) {
  return (
    <div className="form-field">
      <h6 id={`${name}-label`}>{label}</h6>
      <div className="seg" role="radiogroup" aria-labelledby={`${name}-label`}>
        {options.map((option) => (
          <label className="seg-opt" key={option.value}>
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            {option.label}
          </label>
        ))}
      </div>
    </div>
  )
}

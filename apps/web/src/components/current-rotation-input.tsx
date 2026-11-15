import type { RecommendationRequest } from "@croppilot/contracts";
import { RULE_CROPS } from "@/lib/crop-options";

export default function CurrentRotationInput({
  value,
  onChange,
  prefix = "current-rotation",
  badge = "Optional",
}: {
  value: NonNullable<RecommendationRequest["current_rotation"]>;
  onChange: (
    value: NonNullable<RecommendationRequest["current_rotation"]>,
  ) => void;
  prefix?: string;
  badge?: string;
}) {
  function move(index: number, direction: number) {
    const next = [...value];
    [next[index], next[index + direction]] = [
      next[index + direction],
      next[index],
    ];
    onChange(next);
  }
  return (
    <fieldset className="current-rotation" aria-describedby={`${prefix}-help`}>
      <legend>
        Your current rotation <small>{badge}</small>
      </legend>
      <p id={`${prefix}-help`}>
        The crops you usually grow in turn, for example maize then winter wheat.
        We compare every plan with what you do today.
      </p>
      <ol>
        {value.map((crop, index) => (
          <li key={index}>
            <label htmlFor={`${prefix}-${index}`}>
              <span>Crop {index + 1}</span>
              <select
                id={`${prefix}-${index}`}
                value={crop}
                onChange={(event) =>
                  onChange(
                    value.map((entry, position) =>
                      position === index ? event.target.value : entry,
                    ),
                  )
                }
              >
                {RULE_CROPS.map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <div className="rotation-row-actions">
              <button
                type="button"
                disabled={index === 0}
                aria-label={`Move rotation crop ${index + 1} up`}
                onClick={() => move(index, -1)}
              >
                ↑
              </button>
              <button
                type="button"
                disabled={index === value.length - 1}
                aria-label={`Move rotation crop ${index + 1} down`}
                onClick={() => move(index, 1)}
              >
                ↓
              </button>
              <button
                type="button"
                aria-label={`Remove rotation crop ${index + 1}`}
                onClick={() =>
                  onChange(value.filter((_, position) => position !== index))
                }
              >
                Remove
              </button>
            </div>
          </li>
        ))}
      </ol>
      <button
        type="button"
        className="button button--secondary"
        disabled={value.length >= 5}
        onClick={() => onChange([...value, RULE_CROPS[0][0]])}
      >
        Add crop ({value.length}/5)
      </button>
    </fieldset>
  );
}

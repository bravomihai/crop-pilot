import type { RecommendationRequest } from "@croppilot/contracts";
import { RULE_CROPS } from "@/lib/crop-options";
import Icon from "./dashboard/icon";

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
  return (
    <fieldset className="current-rotation" aria-describedby={`${prefix}-help`}>
      <legend>
        Your current rotation <small>{badge}</small>
      </legend>
      <p id={`${prefix}-help`}>
        Add crops in the order you grow them.
      </p>
      <ol className="rotation-crops">
        {value.map((crop, index) => (
          <li className="rotation-crop-row" key={index}>
            <select
              id={`${prefix}-${index}`}
              aria-label={`Rotation crop ${index + 1}`}
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
            <button
              type="button"
              className="button button--secondary rotation-remove"
              aria-label={`Remove rotation crop ${index + 1}`}
              onClick={() =>
                onChange(value.filter((_, position) => position !== index))
              }
            >
              <Icon name="trash" size={17} />
            </button>
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

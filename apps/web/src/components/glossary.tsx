/** Plain explanations of the terms used in the results (named in the Space Apps challenge). */
export const GLOSSARY: readonly { term: string; text: string }[] = [
  {
    term: "Water need covered",
    text: "How much of the water a crop needs was supplied by rain and by water stored in the soil, in percent. 100% means the crop never ran short; below 50% means a severe shortage that usually costs yield.",
  },
  {
    term: "Evapotranspiration (ET₀)",
    text: "The water the air pulls out of soil and plants on a given day, in millimetres. Hot, dry, sunny and windy weather raises it. A crop's own need is ET₀ multiplied by a crop factor that changes as it grows (FAO-56).",
  },
  {
    term: "Water balance",
    text: "A day-by-day account of the soil's water: rain adds, the crop and the sun take away. Roots start shallow and go deeper, so young crops depend on the topsoil, while deep-rooted crops can use water stored over winter.",
  },
  {
    term: "Soil moisture",
    text: "How wet the soil is. The NASA SMAP satellite measures it across the region (the map layer). The plans use a modelled water balance for your point, because satellite pixels are kilometres wide.",
  },
  {
    term: "Heat stress",
    text: "Days above a crop's limit (for example 32 °C for wheat, 35 °C for maize) during flowering and grain filling, when heat does the most damage.",
  },
  {
    term: "Frost risk",
    text: "Nights at or below 0 °C after a spring crop comes up, during flowering, or very cold winter nights for winter crops. Snow cover, which protects winter crops, is not known to the app.",
  },
  {
    term: "Vegetation index (NDVI)",
    text: "A satellite measure of how green and dense plants are, from about 0 (bare soil) to 1 (dense, healthy crop). Low values in the growing season can signal stress.",
  },
  {
    term: "Bare soil",
    text: "Months between harvest and the next sowing with no crop. Bare soil loses water and is washed or blown away more easily; a cover crop protects it.",
  },
  {
    term: "Satellite and regional data vs your field",
    text: "NASA POWER weather covers an area of about 50 km and soil data a 250 m square, so they describe your area, not each part of your field. A soil analysis or your own records always count more.",
  },
  {
    term: "Confidence",
    text: "How much evidence is behind a plan: low, medium or high. It is not a probability of success. Estimated soil data, missing history or serious weather warnings lower it.",
  },
];

/** Why some crop choices help the soil, in a sentence each (also named in the challenge). */
export const CROP_ROLES: readonly { role: string; text: string }[] = [
  {
    role: "Legumes (pea, soybean)",
    text: "Bacteria on their roots take nitrogen from the air, so the next crop needs less fertiliser. They also break disease cycles of cereals.",
  },
  {
    role: "Deep-rooting crops (wheat, maize, sunflower)",
    text: "Reach water and nutrients deep in the soil and loosen it, which helps rain soak in.",
  },
  {
    role: "Drought-tolerant crops (sunflower, sorghum)",
    text: "Keep producing in dry summers, which matters more as hot days become more frequent.",
  },
  {
    role: "Cover crops (vetch, mustard, phacelia)",
    text: "Grown between main crops to protect bare soil from erosion, add organic matter and, for vetch, nitrogen.",
  },
  {
    role: "Changing crop families",
    text: "Growing a different family after a cereal interrupts pests and diseases that survive on the same family.",
  },
];

export default function Glossary() {
  return (
    <details className="glossary" id="glossary">
      <summary>What the terms mean</summary>
      <dl>
        {GLOSSARY.map((entry) => (
          <div key={entry.term}>
            <dt>{entry.term}</dt>
            <dd>{entry.text}</dd>
          </div>
        ))}
      </dl>
      <h4>Why these crop choices help the soil</h4>
      <dl>
        {CROP_ROLES.map((entry) => (
          <div key={entry.role}>
            <dt>{entry.role}</dt>
            <dd>{entry.text}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

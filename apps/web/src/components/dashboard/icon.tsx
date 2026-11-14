const paths = {
  budget: "M3 5h18v15H3Zm0 4h18m-6 4h6v4h-6Z",
  home: "m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z",
  field: "m3 5 8-2 10 3-2 14-9 1-7-6Zm0 0 16 15M11 3l-1 18M3 15l18-9",
  history: "M3 11a9 9 0 1 1 2 7M3 4v7h7m2-4v5l3 2",
  phone:
    "M7 3H4a1 1 0 0 0-1 1c0 9 8 17 17 17a1 1 0 0 0 1-1v-3l-5-2-2 2a14 14 0 0 1-7-7l2-2Z",
  satellite:
    "m9 9 6 6M9 3l3 3-6 6-3-3Zm9 9 3 3-6 6-3-3ZM13 8l3-3 3 3-3 3M4 16a4 4 0 0 1 4 4M3 12a9 9 0 0 1 9 9",
  search: "M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14m5 12 6 6",
  pin: "M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0ZM12 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6",
  area: "M4 8V4h4m8 0h4v4m0 8v4h-4M8 20H4v-4M8 8h8v8H8Z",
  calendar:
    "M8 2v4m8-4v4M3 10h18M4 4h16a1 1 0 0 1 1 1v15a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1",
  draw: "m15 3 6 6M4 14 15 3l6 6-11 11-7 1Z",
  trash: "M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7",
  upload: "M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6",
  file: "M14 2H4v20h16V8Zm0 0v6h6M8 13h8m-8 4h5",
  drop: "M12 2S4 11 4 15a8 8 0 0 0 16 0c0-4-8-13-8-13Z",
  temperature: "M9 14V5a3 3 0 0 1 6 0v9a5 5 0 1 1-6 0Zm3-6v10m6-12h3m-3 4h3",
  leaf: "M4 19C1 8 9 3 21 3c0 12-5 20-17 16Zm-1 3L16 9m-8 8v-6m4 2h6",
  arrow: "M4 12h16m-6-6 6 6-6 6",
  check: "m5 12 4 4L19 6",
  close: "m6 6 12 12M6 18 18 6",
  info: "M12 8h.01M12 11v6M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20",
} as const;

export type IconName = keyof typeof paths;
export default function Icon({
  name,
  size = 20,
}: {
  name: IconName;
  size?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  );
}

import type { CSSProperties } from "react";

const DEMO_REVIEWS = [
  "Fixed the gas leak perfectly but arrived two hours late without calling .",
  "Excellent service , very professional and the price was fair .",
  "Not satisfied with the repair quality , the AC stopped working again .",
  "Slow response and charged extra without explaining why .",
  "Very professional attitude , explained everything clearly before starting .",
];

type Props = {
  selected: string;
  onSelect: (text: string) => void;
};

export function DemoReviewPicker({ selected, onSelect }: Props) {
  return (
    <div style={styles.wrapper}>
      {DEMO_REVIEWS.map((review, i) => {
        const isActive = review === selected;
        return (
          <button
            key={i}
            type="button"
            onClick={() => onSelect(review)}
            style={{
              ...styles.chip,
              borderColor: isActive ? "#0f766e" : "#cbd5e1",
              backgroundColor: isActive ? "#f0fdf9" : "#ffffff",
              color: isActive ? "#0f766e" : "#334155",
              fontWeight: isActive ? 600 : 400,
            }}
          >
            <span style={styles.chipNum}>R{i + 1}</span>
            {review.length > 60 ? review.slice(0, 58) + "…" : review}
          </button>
        );
      })}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  wrapper: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  chip: {
    textAlign: "left",
    padding: "10px 14px",
    borderRadius: "10px",
    border: "1px solid",
    cursor: "pointer",
    fontSize: "13px",
    lineHeight: "1.4",
    transition: "all 150ms ease",
    display: "flex",
    alignItems: "flex-start",
    gap: "10px",
  },
  chipNum: {
    flexShrink: 0,
    fontWeight: 700,
    fontSize: "11px",
    color: "#94a3b8",
    marginTop: "1px",
  },
};

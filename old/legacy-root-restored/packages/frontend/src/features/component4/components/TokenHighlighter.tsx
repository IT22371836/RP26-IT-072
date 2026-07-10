import type { CSSProperties } from "react";
import type { TokenTag } from "../types";

type AspectKey = "QUAL" | "PRICE" | "TIME" | "COMM";

const ASPECT_STYLES: Record<AspectKey, { bg: string; color: string; label: string }> = {
  QUAL:  { bg: "#d1fae5", color: "#065f46", label: "Quality" },
  PRICE: { bg: "#dbeafe", color: "#1e40af", label: "Price" },
  TIME:  { bg: "#fef3c7", color: "#92400e", label: "Time" },
  COMM:  { bg: "#fce7f3", color: "#9d174d", label: "Communication" },
};

function getAspect(tag: string): AspectKey | null {
  for (const key of Object.keys(ASPECT_STYLES) as AspectKey[]) {
    if (tag.includes(key)) return key;
  }
  return null;
}

type Props = { tokens: TokenTag[] };

export function TokenHighlighter({ tokens }: Props) {
  return (
    <div>
      <div style={styles.legend}>
        {(Object.entries(ASPECT_STYLES) as [AspectKey, typeof ASPECT_STYLES[AspectKey]][]).map(
          ([key, s]) => (
            <span key={key} style={{ ...styles.legendItem, backgroundColor: s.bg, color: s.color }}>
              {s.label}
            </span>
          )
        )}
      </div>

      <div style={styles.tokenRow}>
        {tokens.map((t, i) => {
          const aspect = getAspect(t.tag);
          const isBegin = t.tag.startsWith("B-");
          const tokenStyle: CSSProperties = aspect
            ? {
                ...styles.token,
                backgroundColor: ASPECT_STYLES[aspect].bg,
                color: ASPECT_STYLES[aspect].color,
                borderLeft: isBegin ? `3px solid ${ASPECT_STYLES[aspect].color}` : undefined,
              }
            : { ...styles.token, color: "#1e293b" };

          return (
            <span key={i} style={styles.tokenWrap} title={t.tag}>
              <span style={tokenStyle}>{t.token}</span>
              {aspect && <span style={{ ...styles.tagLabel, color: ASPECT_STYLES[aspect].color }}>{t.tag}</span>}
            </span>
          );
        })}
      </div>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  legend: {
    display: "flex",
    flexWrap: "wrap",
    gap: "6px",
    marginBottom: "14px",
  },
  legendItem: {
    padding: "3px 10px",
    borderRadius: "20px",
    fontSize: "12px",
    fontWeight: 600,
  },
  tokenRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "6px",
    lineHeight: "1.6",
  },
  tokenWrap: {
    display: "inline-flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "2px",
  },
  token: {
    padding: "3px 7px",
    borderRadius: "5px",
    fontSize: "14px",
    fontWeight: 500,
  },
  tagLabel: {
    fontSize: "9px",
    fontWeight: 700,
    letterSpacing: "0.3px",
    textTransform: "uppercase" as const,
  },
};

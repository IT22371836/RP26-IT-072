import type { CSSProperties } from "react";
import { SectionCard } from "../../../common/components/ui";
import type { AnalyzeResponse } from "../types";
import { TokenHighlighter } from "./TokenHighlighter";
import { AspectScorePanel } from "./AspectScorePanel";

type Props = { result: AnalyzeResponse };

export function AnalysisResultCard({ result }: Props) {
  const tokenCount = result.tokens.length;
  const ts = new Date(result.timestamp).toLocaleTimeString();

  return (
    <SectionCard title="Analysis Result">
      <div style={styles.section}>
        <p style={styles.sectionLabel}>Tagged Tokens</p>
        <TokenHighlighter tokens={result.tokens} />
      </div>

      <div style={styles.divider} />

      <div style={styles.section}>
        <p style={styles.sectionLabel}>Aspect Confidence Scores</p>
        <AspectScorePanel aspects={result.aspects} />
      </div>

      <p style={styles.footer}>
        {tokenCount} token{tokenCount !== 1 ? "s" : ""} analysed · {ts}
      </p>
    </SectionCard>
  );
}

const styles: Record<string, CSSProperties> = {
  section: {
    marginBottom: "4px",
  },
  sectionLabel: {
    margin: "0 0 10px",
    fontSize: "13px",
    fontWeight: 600,
    color: "#475569",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
  divider: {
    height: "1px",
    backgroundColor: "#e2e8f0",
    margin: "18px 0",
  },
  footer: {
    margin: "18px 0 0",
    fontSize: "12px",
    color: "#94a3b8",
    textAlign: "right",
  },
};

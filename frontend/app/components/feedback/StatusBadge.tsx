import Icon, { type IconName } from "../Icon";

type Tone = "success" | "danger" | "warning" | "info" | "neutral";

const toneIcons: Record<Tone, IconName> = {
  success: "checkCircle",
  danger: "xCircle",
  warning: "alert",
  info: "gauge",
  neutral: "help",
};

export default function StatusBadge({ children, tone = "neutral", icon = true }: { children: React.ReactNode; tone?: Tone; icon?: boolean }) {
  return (
    <span className={`status-badge status-${tone}`}>
      {icon ? <Icon name={toneIcons[tone]} size={14} /> : null}
      {children}
    </span>
  );
}

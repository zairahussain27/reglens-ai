import {
  Search,
  House,
  MessageCircle,
  FileText,
  Landmark,
  ClipboardCheck,
  ChartNoAxesColumnIncreasing,
  Bell,
  UserRound,
  Settings,
  CircleHelp,
  ShieldCheck,
  LogOut,
  type LucideIcon,
} from "lucide-react";

const iconMap: Record<string, LucideIcon> = {
  search: Search,
  home: House,
  ask: MessageCircle,
  regulations: FileText,
  library: FileText,
  filings: FileText,
  business: Landmark,
  assessments: ClipboardCheck,
  risk: ChartNoAxesColumnIncreasing,
  reminders: Bell,
  alerts: Bell,
  reports: ChartNoAxesColumnIncreasing,
  profile: UserRound,
  settings: Settings,
  help: CircleHelp,
  message: MessageCircle,
  compliance: ShieldCheck,
  logout: LogOut,
};

type IconProps = {
  name: string;
  size?: number;
  className?: string;
};

export function Icon({ name, size = 20, className = "" }: IconProps) {
  const LucideIconComponent = iconMap[name] ?? FileText;

  return (
    <LucideIconComponent
      size={size}
      strokeWidth={1.8}
      absoluteStrokeWidth
      className={`app-icon ${className}`}
      aria-hidden="true"
    />
  );
}

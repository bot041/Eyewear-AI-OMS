export function formatOrderNumber(orderNumber: string): string {
  // Strip leading zeros from the numeric part, e.g. ORD0215 -> ORD215
  return orderNumber.replace(/^ORD0+/, "ORD");
}

export function formatSLARemaining(
  hours: number,
  status?: string
): { text: string; isOverdue: boolean; isCritical: boolean } {
  if (status === "Delivered") {
    return {
      text: "Delivered",
      isOverdue: false,
      isCritical: false,
    };
  }

  if (hours <= 0) {
    return {
      text: `Overdue ${Math.min(48, Math.abs(Math.round(hours)))}h`,
      isOverdue: true,
      isCritical: true,
    };
  }

  const totalMinutes = Math.round(hours * 60);
  const days = Math.floor(totalMinutes / (24 * 60));
  const remainingMinutes = totalMinutes % (24 * 60);
  const hrs = Math.floor(remainingMinutes / 60);
  const mins = remainingMinutes % 60;

  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (hrs > 0) parts.push(`${hrs}h`);
  if (days === 0 && hrs === 0 && mins > 0) parts.push(`${mins}m`);
  if (parts.length === 0) parts.push("< 1m");

  return {
    text: `${parts.join(" ")} remaining`,
    isOverdue: false,
    isCritical: hours <= 4,
  };
}

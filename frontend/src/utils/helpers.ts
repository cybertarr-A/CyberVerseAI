export const getSeverityColor = (severity: string) => {
  switch (severity.toLowerCase()) {
    case 'critical':
      return 'text-rose-500 bg-rose-500/10 border-rose-500/20';
    case 'high':
      return 'text-orange-500 bg-orange-500/10 border-orange-500/20';
    case 'medium':
      return 'text-yellow-500 bg-yellow-500/10 border-yellow-500/20';
    case 'low':
      return 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20';
    default:
      return 'text-gray-400 bg-gray-500/10 border-gray-500/20';
  }
};

export const getSeverityBadgeColor = (severity: string) => {
  switch (severity.toLowerCase()) {
    case 'critical':
      return 'bg-rose-500 text-black shadow-[0_0_8px_rgba(244,63,94,0.4)]';
    case 'high':
      return 'bg-orange-500 text-black shadow-[0_0_8px_rgba(249,115,22,0.4)]';
    case 'medium':
      return 'bg-yellow-500 text-black shadow-[0_0_8px_rgba(234,179,8,0.4)]';
    case 'low':
      return 'bg-cyan-500 text-black shadow-[0_0_8px_rgba(6,182,212,0.4)]';
    default:
      return 'bg-gray-500 text-white';
  }
};

export const formatRelativeTime = (timestampString: string): string => {
  try {
    const past = new Date(timestampString);
    const now = new Date();
    const diffMs = now.getTime() - past.getTime();
    const diffSecs = Math.floor(diffMs / 1000);
    
    if (diffSecs < 60) return `${diffSecs}s ago`;
    const diffMins = Math.floor(diffSecs / 60);
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    
    return past.toLocaleDateString();
  } catch {
    return 'Just now';
  }
};

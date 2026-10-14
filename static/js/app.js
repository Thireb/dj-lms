document.addEventListener("alpine:init", () => {
  Alpine.data("countdownCard", () => ({
    remaining: "--:--",
    _timer: null,

    init() {
      const iso = this.$el.dataset.scheduledAt || "";
      if (!isStrictIsoDateTime(iso)) {
        return;
      }
      this.updateRemaining(iso);
      this._timer = window.setInterval(() => this.updateRemaining(iso), 1000);
    },

    destroy() {
      if (this._timer !== null) {
        window.clearInterval(this._timer);
        this._timer = null;
      }
    },

    updateRemaining(iso) {
      const targetMs = Date.parse(iso);
      if (Number.isNaN(targetMs)) {
        this.remaining = "--:--";
        return;
      }
      const diffMs = targetMs - Date.now();
      if (diffMs <= 0) {
        this.remaining = "Started";
        if (this._timer !== null) {
          window.clearInterval(this._timer);
          this._timer = null;
        }
        return;
      }
      this.remaining = `Starts in ${formatRemaining(diffMs)}`;
    },
  }));
});

/** 2d 3h, then 1:02:03, then 04:05. */
function formatRemaining(diffMs) {
  const totalSeconds = Math.floor(diffMs / 1000);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (days > 0) {
    return `${days}d ${hours}h`;
  }
  if (hours > 0) {
    return `${hours}:${pad2(minutes)}:${pad2(seconds)}`;
  }
  return `${pad2(minutes)}:${pad2(seconds)}`;
}

function pad2(value) {
  return String(value).padStart(2, "0");
}

/** Accept ISO 8601 datetimes only (same subset Django parse_datetime handles). */
function isStrictIsoDateTime(value) {
  if (typeof value !== "string" || value.length === 0) {
    return false;
  }
  const isoPattern =
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;
  if (!isoPattern.test(value)) {
    return false;
  }
  return !Number.isNaN(Date.parse(value));
}

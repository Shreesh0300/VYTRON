/**
 * VYTRON — Telemetry Line Charts with Threshold Indicators
 * Powered by Chart.js (with dark theme and dashed warning/critical lines)
 */

const ServerCharts = {
  charts: [null, null, null, null],
  currentServerId: null,

  init() {
    // Canvas contexts are initialized lazily on first update
  },

  updateCharts(serverData) {
    if (!serverData || !serverData.history || !serverData.parameters_meta) return;

    const paramKeys = Object.keys(serverData.parameters_meta);
    const isNewServer = this.currentServerId !== serverData.id;
    this.currentServerId = serverData.id;

    paramKeys.slice(0, 4).forEach((paramKey, idx) => {
      const canvasId = `chartCanvas${idx + 1}`;
      const titleId = `chart1Title`.replace("1", idx + 1);

      const meta = serverData.parameters_meta[paramKey];
      const hist = serverData.history[paramKey] || [];
      const labels = hist.map(pt => pt.time);
      const dataPoints = hist.map(pt => pt.value);

      // Update title with unit
      const titleEl = document.getElementById(titleId);
      if (titleEl) {
        titleEl.textContent = `${meta.name} (${meta.unit})`;
      }

      // Compute threshold lines
      const thresholds = meta.thresholds;
      let warnPoints = [];
      let critPoints = [];

      if (thresholds && thresholds.warning !== undefined) {
        warnPoints = new Array(labels.length).fill(thresholds.warning);
      }
      if (thresholds && thresholds.critical !== undefined) {
        critPoints = new Array(labels.length).fill(thresholds.critical);
      }

      const canvas = document.getElementById(canvasId);
      if (!canvas) return;

      const datasets = [
        {
          label: meta.name,
          data: dataPoints,
          borderColor: "#06b6d4",
          backgroundColor: "rgba(6, 182, 212, 0.12)",
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
        }
      ];

      if (warnPoints.length > 0) {
        datasets.push({
          label: "Warning",
          data: warnPoints,
          borderColor: "#f59e0b",
          borderDash: [5, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
        });
      }

      if (critPoints.length > 0) {
        datasets.push({
          label: "Critical",
          data: critPoints,
          borderColor: "#ef4444",
          borderDash: [5, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
        });
      }

      if (!this.charts[idx] || isNewServer) {
        // Destroy existing instance before recreation
        if (this.charts[idx]) {
          this.charts[idx].destroy();
        }

        const ctx = canvas.getContext("2d");
        this.charts[idx] = new Chart(ctx, {
          type: "line",
          data: {
            labels: labels,
            datasets: datasets,
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 300 },
            interaction: {
              intersect: false,
              mode: "index",
            },
            plugins: {
              legend: { display: false },
              tooltip: {
                backgroundColor: "#131b26",
                borderColor: "rgba(255, 255, 255, 0.1)",
                borderWidth: 1,
                titleFont: { size: 11, family: "JetBrains Mono" },
                bodyFont: { size: 11, family: "JetBrains Mono" },
                padding: 10,
              },
            },
            scales: {
              x: {
                display: true,
                grid: {
                  color: "rgba(255, 255, 255, 0.04)",
                  drawBorder: false,
                },
                ticks: {
                  color: "#64748b",
                  maxTicksLimit: 6,
                  font: { size: 10, family: "JetBrains Mono" },
                },
              },
              y: {
                display: true,
                grid: {
                  color: "rgba(255, 255, 255, 0.04)",
                  drawBorder: false,
                },
                ticks: {
                  color: "#64748b",
                  font: { size: 10, family: "JetBrains Mono" },
                },
                suggestedMin: meta.min !== undefined ? meta.min : undefined,
                suggestedMax: meta.thresholds && meta.thresholds.critical
                  ? Math.max(meta.max, meta.thresholds.critical * 1.15)
                  : undefined,
              },
            },
          },
        });
      } else {
        // Update data in-place
        const chart = this.charts[idx];
        chart.data.labels = labels;
        chart.data.datasets = datasets;
        chart.update("none");
      }
    });
  },

  destroy() {
    this.charts.forEach(chart => {
      if (chart) chart.destroy();
    });
    this.charts = [null, null, null, null];
  }
};

window.ServerCharts = ServerCharts;

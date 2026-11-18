// View module: renders DOM controls, table rows, and Chart.js line chart.
const MISSING = "\u2014";
const numberFormat = new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
});

function cssVar(name) {
    return getComputedStyle(document.documentElement)
        .getPropertyValue(name)
        .trim();
}

export class PeriodAveragesView {
    constructor(maxCountries) {
        this.maxCountries = maxCountries;
        this.indicatorSelect = document.getElementById("indicator");
        this.regionSelect = document.getElementById("region");
        this.periodYearsSelect = document.getElementById("period-years");
        this.sexSelect = document.getElementById("sex");
        this.countrySummary = document.getElementById("country-summary");
        this.countryList = document.getElementById("country-list");
        this.statusEl = document.getElementById("status");
        this.chartCanvas = document.getElementById("averages-chart");
        this.tableEl = document.getElementById("averages-table");
        this.chart = null;
    }

    renderIndicators(indicators, selectedCode) {
        this.indicatorSelect.replaceChildren();
        for (const item of indicators) {
            const opt = document.createElement("option");
            opt.value = item.code;
            opt.textContent = `${item.name} (${item.code})`;
            opt.selected = item.code === selectedCode;
            this.indicatorSelect.append(opt);
        }
    }

    renderRegions(regions, selectedRegion) {
        this.regionSelect.replaceChildren();
        const allOpt = document.createElement("option");
        allOpt.value = "";
        allOpt.textContent = "All regions";
        allOpt.selected = selectedRegion === "";
        this.regionSelect.append(allOpt);

        for (const region of regions) {
            const opt = document.createElement("option");
            opt.value = region;
            opt.textContent = region;
            opt.selected = region === selectedRegion;
            this.regionSelect.append(opt);
        }
    }

    renderPeriodYears(options, selectedYears) {
        this.periodYearsSelect.replaceChildren();
        for (const years of options) {
            const opt = document.createElement("option");
            opt.value = String(years);
            opt.textContent = years === 1 ? "1 year" : `${years} years`;
            opt.selected = years === selectedYears;
            this.periodYearsSelect.append(opt);
        }
    }

    renderSexOptions(options, selectedSex) {
        this.sexSelect.replaceChildren();
        for (const item of options) {
            const opt = document.createElement("option");
            opt.value = item.value;
            opt.textContent = item.label;
            opt.selected = item.value === selectedSex;
            this.sexSelect.append(opt);
        }
    }

    renderCountries(countries, selectedIso3s) {
        const selectedSet = new Set(selectedIso3s);
        const atLimit = selectedSet.size >= this.maxCountries;
        this.countryList.replaceChildren();

        for (const country of countries) {
            const li = document.createElement("li");
            const label = document.createElement("label");
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.value = country.iso3;
            checkbox.checked = selectedSet.has(country.iso3);
            checkbox.disabled = atLimit && !checkbox.checked;

            const text = document.createTextNode(
                `${country.name} (${country.iso3})`
            );
            label.append(checkbox, text);
            li.append(label);
            this.countryList.append(li);
        }
        this.updateCountrySummary(selectedSet.size);
    }

    updateCountrySummary(count) {
        if (count === 0) {
            this.countrySummary.textContent = "Choose countries";
        } else {
            this.countrySummary.textContent = `${count} of ${this.maxCountries} selected`;
        }
    }

    showStatus(message, { isError = false } = {}) {
        this.statusEl.textContent = message;
        this.statusEl.classList.toggle("status-error", isError);
    }

    clearResults() {
        this.tableEl.replaceChildren();
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }

    renderTable(tableModel) {
        this.tableEl.replaceChildren();
        const thead = document.createElement("thead");
        const headRow = document.createElement("tr");
        tableModel.headers.forEach((header, idx) => {
            const th = document.createElement("th");
            if (idx > 0) {
                th.className = "number";
            }
            th.textContent = header;
            headRow.append(th);
        });
        thead.append(headRow);

        const tbody = document.createElement("tbody");
        for (const row of tableModel.rows) {
            const tr = document.createElement("tr");
            const countryCell = document.createElement("td");
            countryCell.textContent = row.country;
            tr.append(countryCell);

            for (const value of row.cells) {
                const cell = document.createElement("td");
                cell.className = "number";
                cell.textContent =
                    value === null ? MISSING : numberFormat.format(value);
                tr.append(cell);
            }
            tbody.append(tr);
        }
        this.tableEl.append(thead, tbody);
    }

    renderChart(chartModel) {
        if (this.chart) {
            this.chart.destroy();
        }
        const textColor = cssVar("--text-secondary") || "#6e6e73";
        const gridColor = cssVar("--chart-grid") || "rgba(0,0,0,0.08)";

        const datasets = chartModel.lines.map((line) => {
            const color = cssVar(`--series-${line.colorSlot}`) || "#0071e3";
            return {
                label: line.label,
                data: line.values,
                borderColor: color,
                backgroundColor: color,
                tension: 0.2,
                spanGaps: false,
                pointRadius: 4,
                pointHoverRadius: 6,
            };
        });

        this.chart = new window.Chart(this.chartCanvas, {
            type: "line",
            data: {
                labels: chartModel.labels,
                datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: "index",
                    intersect: false,
                },
                plugins: {
                    legend: {
                        labels: {
                            color: textColor,
                        },
                    },
                },
                scales: {
                    x: {
                        ticks: { color: textColor },
                        grid: { color: gridColor },
                    },
                    y: {
                        title: {
                            display: true,
                            text: chartModel.yTitle,
                            color: textColor,
                        },
                        ticks: { color: textColor },
                        grid: { color: gridColor },
                    },
                },
            },
        });
    }
}

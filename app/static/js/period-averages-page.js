// Page controller module: wires user events, AbortController, model, and view.
import {
    fetchCountries,
    fetchIndicators,
    fetchPeriodAverages,
    fetchRegions,
} from "./api-client.js";
import {
    ColorSlots,
    DEFAULTS,
    PERIOD_LENGTH_OPTIONS,
    SEX_OPTIONS,
    pickDefaultCountries,
    pickDefaultValue,
    toChart,
    toTable,
} from "./period-averages-model.js";
import { PeriodAveragesView } from "./period-averages-view.js";

class PeriodAveragesPage {
    constructor(rootEl) {
        this.firstYear = Number(rootEl.dataset.firstYear || 2000);
        this.lastYear = Number(rootEl.dataset.lastYear || 2023);
        this.maxCountries = Number(rootEl.dataset.maxCountries || 8);

        this.view = new PeriodAveragesView(this.maxCountries);
        this.colorSlots = new ColorSlots(this.maxCountries);
        this.countries = [];
        this.selectedIso3s = [];
        this.report = null;
        this.pendingRequest = null;
        this.countryRequest = null;
    }

    currentQuery() {
        return {
            indicatorCode: this.view.indicatorSelect.value,
            firstYear: this.firstYear,
            lastYear: this.lastYear,
            periodYears: Number(this.view.periodYearsSelect.value),
            sex: this.view.sexSelect.value,
            countryIso3s: this.selectedIso3s,
        };
    }

    async start() {
        this.view.showStatus("Loading filters\u2026");
        this.view.renderPeriodYears(PERIOD_LENGTH_OPTIONS, DEFAULTS.periodYears);
        this.view.renderSexOptions(SEX_OPTIONS, DEFAULTS.sex);

        try {
            const [indicators, regions] = await Promise.all([
                fetchIndicators(),
                fetchRegions(),
            ]);
            const defaultIndicator = pickDefaultValue(
                indicators,
                DEFAULTS.indicatorCode,
                (item) => item.code
            );
            const defaultRegion = pickDefaultValue(regions, DEFAULTS.region);

            this.view.renderIndicators(indicators, defaultIndicator);
            this.view.renderRegions(regions, defaultRegion);

            await this.loadCountries(defaultRegion, { useDefaults: true });
            this.bindEvents();
            await this.refresh();
        } catch (error) {
            this.view.showStatus(
                `Could not initialize page: ${error.message}`,
                { isError: true }
            );
        }
    }

    async loadCountries(region, { useDefaults = false } = {}) {
        this.countryRequest?.abort();
        const request = new AbortController();
        this.countryRequest = request;

        try {
            this.countries = await fetchCountries(region, request.signal);
        } catch (error) {
            if (error.name !== "AbortError") {
                this.view.showStatus(
                    `Could not load countries: ${error.message}`,
                    { isError: true }
                );
            }
            return;
        }

        if (useDefaults) {
            this.selectedIso3s = pickDefaultCountries(
                this.countries,
                DEFAULTS.countryIso3s,
                5
            );
        } else {
            const available = new Set(this.countries.map((c) => c.iso3));
            const kept = this.selectedIso3s.filter((iso3) => available.has(iso3));
            this.selectedIso3s =
                kept.length > 0
                    ? kept
                    : pickDefaultCountries(this.countries, [], 5);
        }

        this.view.renderCountries(this.countries, this.selectedIso3s);
    }

    bindEvents() {
        this.view.indicatorSelect.addEventListener("change", () =>
            this.refresh()
        );
        this.view.periodYearsSelect.addEventListener("change", () =>
            this.refresh()
        );
        this.view.sexSelect.addEventListener("change", () => this.refresh());
        this.view.regionSelect.addEventListener("change", async () => {
            await this.loadCountries(this.view.regionSelect.value);
            await this.refresh();
        });
        this.view.countryList.addEventListener("change", (event) => {
            if (event.target.type !== "checkbox") {
                return;
            }
            const checked = Array.from(
                this.view.countryList.querySelectorAll("input:checked")
            ).map((input) => input.value);
            this.selectedIso3s = checked.slice(0, this.maxCountries);
            this.view.renderCountries(this.countries, this.selectedIso3s);
            this.refresh();
        });
    }

    renderReport() {
        if (!this.report) {
            return;
        }
        const tableModel = toTable(this.report);
        const chartModel = toChart(this.report, this.colorSlots);
        this.view.renderChart(chartModel);
        this.view.renderTable(tableModel);

        const count = this.report.series.length;
        const label = count === 1 ? "country" : "countries";
        this.view.showStatus(
            `Showing ${this.report.indicator.name} for ${count} ${label}.`
        );
    }

    async refresh() {
        // Only the answer to the latest filters may be drawn.
        this.pendingRequest?.abort();
        if (this.selectedIso3s.length === 0) {
            this.view.clearResults();
            this.view.showStatus("Choose at least one country.");
            return;
        }
        const request = new AbortController();
        this.pendingRequest = request;
        this.view.showStatus("Loading\u2026");

        try {
            this.report = await fetchPeriodAverages(
                this.currentQuery(),
                request.signal
            );
        } catch (error) {
            if (error.name !== "AbortError") {
                this.view.clearResults();
                this.view.showStatus(
                    `Could not load the data: ${error.message}`,
                    { isError: true }
                );
            }
            return;
        }

        this.colorSlots.update(this.selectedIso3s);
        this.renderReport();
    }
}

const rootEl = document.getElementById("period-averages-app");
if (rootEl) {
    new PeriodAveragesPage(rootEl).start();
}

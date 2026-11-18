// Pure model module: defaults, stable color slots, and report -> table/chart transformations.
export const DEFAULTS = {
    indicatorCode: "OWID_LIFE_EXPECTANCY",
    region: "Europe & Central Asia",
    periodYears: 5,
    sex: "BTSX",
    countryIso3s: ["FRA", "DEU", "ITA", "ROU", "ESP"],
};

export const PERIOD_LENGTH_OPTIONS = [1, 2, 3, 5, 10];

export const SEX_OPTIONS = [
    { value: "BTSX", label: "Both sexes" },
    { value: "FMLE", label: "Female" },
    { value: "MLE", label: "Male" },
];

export class ColorSlots {
    constructor(maxSlots = 8) {
        this.maxSlots = maxSlots;
        this.slots = new Map();
    }

    update(selectedIso3s) {
        const active = new Set(selectedIso3s);
        for (const iso3 of this.slots.keys()) {
            if (!active.has(iso3)) {
                this.slots.delete(iso3);
            }
        }
        for (const iso3 of selectedIso3s) {
            if (!this.slots.has(iso3)) {
                const used = new Set(this.slots.values());
                for (let slot = 1; slot <= this.maxSlots; slot += 1) {
                    if (!used.has(slot)) {
                        this.slots.set(iso3, slot);
                        break;
                    }
                }
            }
        }
    }

    slotOf(iso3) {
        return this.slots.get(iso3) ?? 1;
    }
}

export function pickDefaultValue(items, preferred, getValue = (item) => item) {
    const values = items.map(getValue);
    if (values.includes(preferred)) {
        return preferred;
    }
    return values[0] ?? "";
}

export function pickDefaultCountries(countries, preferredIso3s, limit = 5) {
    const available = new Set(countries.map((c) => c.iso3));
    const matched = preferredIso3s.filter((iso3) => available.has(iso3));
    if (matched.length > 0) {
        return matched.slice(0, limit);
    }
    return countries.slice(0, limit).map((c) => c.iso3);
}

export function axisTitle(indicator) {
    return indicator.unit
        ? `${indicator.name} (${indicator.unit})`
        : indicator.name;
}

export function toTable(report) {
    return {
        headers: ["Country", ...report.periods.map((period) => period.label)],
        rows: report.series.map((series) => ({
            country: `${series.country_name} (${series.country_iso3})`,
            cells: series.averages,
        })),
    };
}

export function toChart(report, colorSlots) {
    return {
        labels: report.periods.map((period) => period.label),
        yTitle: axisTitle(report.indicator),
        lines: report.series.map((series) => ({
            label: series.country_name,
            values: series.averages,
            colorSlot: colorSlots.slotOf(series.country_iso3),
        })),
    };
}

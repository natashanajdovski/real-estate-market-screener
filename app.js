// Real Estate Market Screener - Main Application

let allMetros = [];
let filteredMetros = [];
let currentSort = { column: 'composite_score', direction: 'desc' };
let dataTimestamp = '';
let selectedStates = new Set();
let allStates = [];

// Scoring weights (must match build_dataset.py)
const WEIGHTS = {
    gross_yield: 0.30,
    population_growth: 0.20,
    job_growth: 0.15,
    rent_growth: 0.15,
    landlord_score: 0.10,
    vacancy_rate: 0.10
};

// Initialize app
document.addEventListener('DOMContentLoaded', async () => {
    await loadData();
    setupEventListeners();
    applyFilters();
});

// Load data from JSON
async function loadData() {
    try {
        const response = await fetch('data/metros.json');
        const data = await response.json();
        allMetros = data.metros;
        dataTimestamp = data.generated;

        // Update last updated
        document.getElementById('lastUpdated').textContent = new Date(dataTimestamp).toLocaleDateString();

        // Populate state exclusion dropdown
        populateStateFilter();
    } catch (error) {
        console.error('Error loading data:', error);
        document.getElementById('metroTableBody').innerHTML = `
            <tr><td colspan="10" class="empty-state">
                <h3>Error loading data</h3>
                <p>Please ensure data/metros.json exists.</p>
            </td></tr>
        `;
    }
}

// Populate state dropdown
function populateStateFilter() {
    allStates = [...new Set(allMetros.map(m => m.state).filter(Boolean))].sort();

    // Select all states by default
    selectedStates = new Set(allStates);

    // Render state options
    renderStateOptions();

    // Toggle dropdown open/close
    document.getElementById('stateDropdownBtn').addEventListener('click', () => {
        const dropdown = document.getElementById('stateDropdown');
        dropdown.classList.toggle('open');
        if (dropdown.classList.contains('open')) {
            document.getElementById('stateSearch').focus();
        }
    });

    // Search functionality
    document.getElementById('stateSearch').addEventListener('input', (e) => {
        renderStateOptions(e.target.value.toLowerCase());
    });

    // Prevent dropdown close when clicking inside search
    document.getElementById('stateSearch').addEventListener('click', (e) => {
        e.stopPropagation();
    });

    // Select All button
    document.getElementById('selectAllStates').addEventListener('click', (e) => {
        e.stopPropagation();
        selectedStates = new Set(allStates);
        renderStateOptions(document.getElementById('stateSearch').value.toLowerCase());
        updateStateDropdownUI();
        applyFilters();
    });

    // Deselect All button
    document.getElementById('deselectAllStates').addEventListener('click', (e) => {
        e.stopPropagation();
        selectedStates.clear();
        renderStateOptions(document.getElementById('stateSearch').value.toLowerCase());
        updateStateDropdownUI();
        applyFilters();
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        const dropdown = document.getElementById('stateDropdown');
        if (!dropdown.contains(e.target)) {
            dropdown.classList.remove('open');
            document.getElementById('stateSearch').value = '';
            renderStateOptions();
        }
    });
}

// Render state options (with optional search filter)
function renderStateOptions(searchTerm = '') {
    const container = document.getElementById('stateOptionsList');
    const filteredStates = searchTerm
        ? allStates.filter(state => state.toLowerCase().includes(searchTerm))
        : allStates;

    container.innerHTML = filteredStates.map(state => `
        <div class="state-option ${selectedStates.has(state) ? 'selected' : ''}" data-state="${state}">
            <span class="state-option-checkbox"></span>
            <span>${state}</span>
        </div>
    `).join('');

    // Add click handlers to each option
    container.querySelectorAll('.state-option').forEach(option => {
        option.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleStateSelection(option.dataset.state);
            renderStateOptions(searchTerm);
        });
    });
}

// Toggle state selection
function toggleStateSelection(state) {
    if (selectedStates.has(state)) {
        selectedStates.delete(state);
    } else {
        selectedStates.add(state);
    }

    updateStateDropdownUI();
    applyFilters();
}

// Update the dropdown UI to reflect current selections
function updateStateDropdownUI() {
    // Update option styles
    document.querySelectorAll('.state-option').forEach(option => {
        if (selectedStates.has(option.dataset.state)) {
            option.classList.add('selected');
        } else {
            option.classList.remove('selected');
        }
    });

    // Update button label
    const label = document.getElementById('stateDropdownLabel');
    const excludedCount = allStates.length - selectedStates.size;

    if (excludedCount === 0) {
        label.textContent = 'All States';
        label.style.color = '';
    } else if (selectedStates.size === 0) {
        label.textContent = 'No States Selected';
        label.style.color = 'var(--danger)';
    } else {
        label.textContent = `${excludedCount} state${excludedCount > 1 ? 's' : ''} excluded`;
        label.style.color = 'var(--warning)';
    }
}

// Setup event listeners
function setupEventListeners() {
    // Filter inputs
    document.getElementById('maxPrice').addEventListener('input', handlePriceChange);
    document.getElementById('minYield').addEventListener('input', handleYieldChange);
    document.getElementById('maxAirportDist').addEventListener('input', handleAirportDistChange);
    document.getElementById('marketType').addEventListener('change', applyFilters);

    // Buttons
    document.getElementById('resetFilters').addEventListener('click', resetFilters);
    document.getElementById('exportExcel').addEventListener('click', exportToExcel);

    // Table sorting
    document.querySelectorAll('th.sortable').forEach(th => {
        th.addEventListener('click', () => handleSort(th.dataset.sort));
    });

    // Modal
    document.querySelector('.close').addEventListener('click', closeModal);
    document.getElementById('detailModal').addEventListener('click', (e) => {
        if (e.target === document.getElementById('detailModal')) closeModal();
    });
}

// Filter handlers
function handlePriceChange(e) {
    document.getElementById('maxPriceValue').textContent = formatCurrency(e.target.value);
    applyFilters();
}

function handleYieldChange(e) {
    document.getElementById('minYieldValue').textContent = e.target.value + '%';
    applyFilters();
}

function handleAirportDistChange(e) {
    document.getElementById('maxAirportDistValue').textContent = e.target.value + ' mi';
    applyFilters();
}

// Apply all filters
function applyFilters() {
    const maxPrice = parseInt(document.getElementById('maxPrice').value);
    const minYield = parseFloat(document.getElementById('minYield').value);
    const maxAirportDist = parseInt(document.getElementById('maxAirportDist').value);
    const marketType = document.getElementById('marketType').value;

    filteredMetros = allMetros.filter(metro => {
        // Price filter
        if (metro.median_price > maxPrice) return false;

        // Yield filter
        if (metro.gross_yield < minYield) return false;

        // Airport distance filter
        if (metro.airport_distance_miles && metro.airport_distance_miles > maxAirportDist) return false;

        // Market type filter
        if (marketType !== 'all' && metro.market_type !== marketType) return false;

        // State selection filter
        if (!selectedStates.has(metro.state)) return false;

        return true;
    });

    // Sort
    sortMetros();

    // Update table
    renderTable();

    // Update count
    const excludedCount = allStates.length - selectedStates.size;
    const excludedText = excludedCount > 0 ? ` (${excludedCount} state${excludedCount > 1 ? 's' : ''} excluded)` : '';
    document.getElementById('resultCount').textContent = `${filteredMetros.length} of ${allMetros.length} markets${excludedText}`;
}

// Reset filters
function resetFilters() {
    document.getElementById('maxPrice').value = 300000;
    document.getElementById('maxPriceValue').textContent = '$300,000';

    document.getElementById('minYield').value = 5;
    document.getElementById('minYieldValue').textContent = '5%';

    document.getElementById('maxAirportDist').value = 30;
    document.getElementById('maxAirportDistValue').textContent = '30 mi';

    document.getElementById('marketType').value = 'all';

    // Select all states
    selectedStates = new Set(allStates);
    updateStateDropdownUI();

    applyFilters();
}

// Sort metros
function sortMetros() {
    const { column, direction } = currentSort;
    const multiplier = direction === 'asc' ? 1 : -1;

    filteredMetros.sort((a, b) => {
        let aVal = a[column];
        let bVal = b[column];

        // Handle nulls
        if (aVal === null || aVal === undefined) aVal = direction === 'asc' ? Infinity : -Infinity;
        if (bVal === null || bVal === undefined) bVal = direction === 'asc' ? Infinity : -Infinity;

        // Handle strings
        if (typeof aVal === 'string') {
            return aVal.localeCompare(bVal) * multiplier;
        }

        return (aVal - bVal) * multiplier;
    });
}

// Handle sort click
function handleSort(column) {
    // Update sort direction
    if (currentSort.column === column) {
        currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
    } else {
        currentSort.column = column;
        currentSort.direction = 'desc';
    }

    // Update header styles
    document.querySelectorAll('th.sortable').forEach(th => {
        th.classList.remove('sorted-asc', 'sorted-desc');
        if (th.dataset.sort === column) {
            th.classList.add(currentSort.direction === 'asc' ? 'sorted-asc' : 'sorted-desc');
        }
    });

    // Re-sort and render
    sortMetros();
    renderTable();
}

// Render table
function renderTable() {
    const tbody = document.getElementById('metroTableBody');

    if (filteredMetros.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="11" class="empty-state">
                <h3>No markets match your criteria</h3>
                <p>Try adjusting your filters to see more results.</p>
            </td></tr>
        `;
        return;
    }

    tbody.innerHTML = filteredMetros.map((metro, index) => `
        <tr data-id="${metro.region_id}" onclick="openDetail(${metro.region_id})">
            <td>${index + 1}</td>
            <td><strong>${metro.name}</strong></td>
            <td>${getMarketTypeTag(metro.market_type)}</td>
            <td class="${getScoreClass(metro.composite_score)}">${metro.composite_score}</td>
            <td>${formatCurrency(metro.median_price)}</td>
            <td>${metro.gross_yield.toFixed(2)}%</td>
            <td>${formatGrowth(metro.pop_growth_yoy)}</td>
            <td>${formatGrowth(metro.job_growth_yoy)}</td>
            <td class="${getCrimeClass(metro.crime_rate)}">${metro.crime_rate ? metro.crime_rate.toFixed(0) : '-'}</td>
            <td>${metro.airport_distance_miles ? metro.airport_distance_miles + ' mi' : '-'}</td>
            <td><a href="${getZillowUrl(metro)}" target="_blank" class="zillow-link" onclick="event.stopPropagation()">View</a></td>
        </tr>
    `).join('');
}

// Get market type tag HTML
function getMarketTypeTag(type) {
    if (!type) return '-';

    const classes = {
        'High Yield': 'tag-high-yield',
        'Growth': 'tag-growth',
        'Both': 'tag-both'
    };

    return `<span class="tag ${classes[type]}">${type}</span>`;
}

// Get score class
function getScoreClass(score) {
    if (score >= 60) return 'score-high';
    if (score >= 45) return 'score-medium';
    return 'score-low';
}

// Get crime rate class (lower is better)
function getCrimeClass(rate) {
    if (rate === null || rate === undefined) return '';
    if (rate <= 300) return 'score-high';  // Low crime = good (green)
    if (rate <= 500) return 'score-medium'; // Medium crime (yellow)
    return 'score-low';  // High crime = bad (gray/red)
}

// Generate Zillow search URL for a metro (filtered for 1950-1975 single family homes)
function getZillowUrl(metro) {
    // Extract the primary city from metro name (e.g., "Joplin, MO" -> "joplin")
    const city = metro.name.split(',')[0].split('-')[0].trim().toLowerCase().replace(/\s+/g, '-');
    const state = metro.state.toLowerCase();

    // Build search query with filters for single family homes built 1950-1975
    const searchQuery = {
        filterState: {
            sort: { value: "days" },           // Sort by newest listings
            sf: { value: false },              // Include single family (false = not excluded)
            tow: { value: false },             // Include townhouses
            mf: { value: false },              // Include multi-family
            con: { value: false },             // Include condos
            land: { value: false },            // Include land
            apa: { value: false },             // Include apartments
            manu: { value: false },            // Include manufactured
            built: {                           // Year built filter
                min: 1950,
                max: 1975
            }
        },
        isListVisible: true
    };

    const encoded = encodeURIComponent(JSON.stringify(searchQuery));
    return `https://www.zillow.com/${city}-${state}/?searchQueryState=${encoded}`;
}

// Format currency
function formatCurrency(value) {
    return '$' + parseInt(value).toLocaleString();
}

// Format growth percentage
function formatGrowth(value) {
    if (value === null || value === undefined) return '-';
    const formatted = value.toFixed(2) + '%';
    if (value > 0) return '+' + formatted;
    return formatted;
}

// Calculate component scores for a metro (matching build_dataset.py logic)
function calculateScoreBreakdown(metro) {
    const breakdown = {};

    // Gross yield (higher is better, cap at 12% for normalization)
    if (metro.gross_yield != null) {
        breakdown.gross_yield = {
            raw: metro.gross_yield,
            normalized: Math.min(metro.gross_yield / 12 * 100, 100),
            weight: WEIGHTS.gross_yield,
            weighted: Math.min(metro.gross_yield / 12 * 100, 100) * WEIGHTS.gross_yield,
            source: 'Zillow ZORI/ZHVI (Dec 2025)',
            sourceUrl: 'https://www.zillow.com/research/data/',
            formula: '(Monthly Rent × 12) / Median Price × 100',
            normalization: 'Scaled 0-12% → 0-100 (capped at 12%)'
        };
    }

    // Population growth (higher is better, normalize around -1% to 3%)
    if (metro.pop_growth_yoy != null) {
        const normalized = Math.max(0, Math.min(100, (metro.pop_growth_yoy + 1) / 4 * 100));
        breakdown.population_growth = {
            raw: metro.pop_growth_yoy,
            normalized: normalized,
            weight: WEIGHTS.population_growth,
            weighted: normalized * WEIGHTS.population_growth,
            source: 'Census Bureau CBSA Estimates',
            sourceUrl: 'https://www.census.gov/data/tables/time-series/demo/popest/2020s-total-metro-and-micro-statistical-areas.html',
            formula: '(Pop 2024 - Pop 2023) / Pop 2023 × 100',
            normalization: 'Scaled -1% to +3% → 0-100'
        };
    }

    // Job growth (higher is better, normalize around -2% to 5%)
    if (metro.job_growth_yoy != null) {
        const normalized = Math.max(0, Math.min(100, (metro.job_growth_yoy + 2) / 7 * 100));
        breakdown.job_growth = {
            raw: metro.job_growth_yoy,
            normalized: normalized,
            weight: WEIGHTS.job_growth,
            weighted: normalized * WEIGHTS.job_growth,
            source: 'BLS Quarterly Census of Employment & Wages',
            sourceUrl: 'https://www.bls.gov/cew/',
            formula: 'YoY % change in private sector employment',
            normalization: 'Scaled -2% to +5% → 0-100'
        };
    }

    // Rent growth (higher is better, normalize around -2% to 8%)
    if (metro.rent_growth_yoy != null) {
        const normalized = Math.max(0, Math.min(100, (metro.rent_growth_yoy + 2) / 10 * 100));
        breakdown.rent_growth = {
            raw: metro.rent_growth_yoy,
            normalized: normalized,
            weight: WEIGHTS.rent_growth,
            weighted: normalized * WEIGHTS.rent_growth,
            source: 'Zillow ZORI (Dec 2025)',
            sourceUrl: 'https://www.zillow.com/research/data/',
            formula: '(Rent now - Rent 12mo ago) / Rent 12mo ago × 100',
            normalization: 'Scaled -2% to +8% → 0-100'
        };
    }

    // Landlord score (already 1-10, convert to 0-100)
    if (metro.landlord_score != null) {
        breakdown.landlord_score = {
            raw: metro.landlord_score,
            normalized: metro.landlord_score * 10,
            weight: WEIGHTS.landlord_score,
            weighted: metro.landlord_score * 10 * WEIGHTS.landlord_score,
            source: 'Manual research (eviction laws, rent control, etc.)',
            sourceUrl: 'https://www.nolo.com/legal-encyclopedia/state-laws-on-termination-for-nonpayment-of-rent.html',
            formula: 'State-level 1-10 rating',
            normalization: 'Scaled 1-10 → 10-100'
        };
    }

    // Vacancy rate (lower is better, normalize 0-20%)
    if (metro.vacancy_rate != null) {
        const normalized = Math.max(0, 100 - (metro.vacancy_rate / 20 * 100));
        breakdown.vacancy_rate = {
            raw: metro.vacancy_rate,
            normalized: normalized,
            weight: WEIGHTS.vacancy_rate,
            weighted: normalized * WEIGHTS.vacancy_rate,
            source: 'Census ACS Table B25002',
            sourceUrl: 'https://data.census.gov/table?q=B25002',
            formula: 'Vacant Units / Total Units × 100',
            normalization: 'Inverted: 0-20% vacancy → 100-0 score'
        };
    }

    // Calculate totals
    let totalWeight = 0;
    let weightedSum = 0;
    for (const key in breakdown) {
        weightedSum += breakdown[key].weighted;
        totalWeight += breakdown[key].weight;
    }

    // Adjust for missing data
    const adjustmentFactor = totalWeight / Object.values(WEIGHTS).reduce((a, b) => a + b, 0);
    const finalScore = totalWeight > 0 ? (weightedSum / totalWeight) * adjustmentFactor : 0;

    return {
        components: breakdown,
        totalWeight,
        weightedSum,
        adjustmentFactor,
        finalScore: Math.round(finalScore * 10) / 10
    };
}

// Open detail modal
function openDetail(regionId) {
    const metro = allMetros.find(m => m.region_id === regionId);
    if (!metro) return;

    const modal = document.getElementById('detailModal');
    const content = document.getElementById('modalContent');

    // Calculate score breakdown
    const breakdown = calculateScoreBreakdown(metro);

    content.innerHTML = `
        <div class="modal-header">
            <h2>${metro.name}</h2>
            ${getMarketTypeTag(metro.market_type)}
            <span style="margin-left: 1rem; font-size: 1.25rem;" class="${getScoreClass(metro.composite_score)}">
                Score: ${metro.composite_score}
            </span>
        </div>

        <div class="modal-stats">
            <div class="stat-card">
                <label>Median Home Price</label>
                <div class="value">${formatCurrency(metro.median_price)}</div>
                <a href="https://www.zillow.com/research/data/" target="_blank">Source: Zillow ZHVI</a>
            </div>
            <div class="stat-card">
                <label>Monthly Rent</label>
                <div class="value">${formatCurrency(metro.monthly_rent)}</div>
                <a href="https://www.zillow.com/research/data/" target="_blank">Source: Zillow ZORI</a>
            </div>
            <div class="stat-card">
                <label>Gross Rental Yield</label>
                <div class="value">${metro.gross_yield.toFixed(2)}%</div>
                <small>Annual rent / price</small>
            </div>
            <div class="stat-card">
                <label>Rent Growth (YoY)</label>
                <div class="value ${metro.rent_growth_yoy > 0 ? 'positive' : metro.rent_growth_yoy < 0 ? 'negative' : ''}">
                    ${formatGrowth(metro.rent_growth_yoy)}
                </div>
            </div>
            <div class="stat-card">
                <label>Population Growth (YoY)</label>
                <div class="value ${metro.pop_growth_yoy > 0 ? 'positive' : metro.pop_growth_yoy < 0 ? 'negative' : ''}">
                    ${formatGrowth(metro.pop_growth_yoy)}
                </div>
                <a href="https://www.census.gov/data.html" target="_blank">Source: Census Bureau</a>
            </div>
            <div class="stat-card">
                <label>Job Growth (YoY)</label>
                <div class="value ${metro.job_growth_yoy > 0 ? 'positive' : metro.job_growth_yoy < 0 ? 'negative' : ''}">
                    ${formatGrowth(metro.job_growth_yoy)}
                </div>
                <a href="https://www.bls.gov/cew/" target="_blank">Source: BLS QCEW</a>
            </div>
            <div class="stat-card">
                <label>Vacancy Rate</label>
                <div class="value">${metro.vacancy_rate ? metro.vacancy_rate.toFixed(1) + '%' : '-'}</div>
                <a href="https://data.census.gov/table?q=B25002" target="_blank">Source: Census ACS</a>
            </div>
            <div class="stat-card">
                <label>Landlord Score</label>
                <div class="value">${metro.landlord_score || '-'}/10</div>
                <small>Higher = more landlord-friendly</small>
            </div>
            <div class="stat-card">
                <label>Nearest Major Airport</label>
                <div class="value">${metro.nearest_airport || '-'}</div>
                <small>${metro.airport_distance_miles ? metro.airport_distance_miles + ' miles' : ''}</small>
            </div>
            <div class="stat-card">
                <label>Population (2024)</label>
                <div class="value">${metro.population ? metro.population.toLocaleString() : '-'}</div>
            </div>
            <div class="stat-card">
                <label>Violent Crime Rate</label>
                <div class="value">${metro.crime_rate ? metro.crime_rate.toFixed(0) + '/100k' : '-'}</div>
                <a href="https://cde.ucr.cjis.gov/" target="_blank">Source: FBI 2023 (state-level)</a>
            </div>
        </div>

        <div class="score-breakdown">
            <h3>Score Breakdown</h3>
            <p class="breakdown-explanation">
                The composite score (0-100) is a weighted average of 6 factors. Each raw metric is normalized to a 0-100 scale,
                then multiplied by its weight. If data is missing for some factors, the score is adjusted proportionally.
            </p>
            <table class="breakdown-table">
                <thead>
                    <tr>
                        <th>Factor</th>
                        <th>Weight</th>
                        <th>Raw Value</th>
                        <th>Normalized (0-100)</th>
                        <th>Weighted Score</th>
                        <th>Source</th>
                    </tr>
                </thead>
                <tbody>
                    ${Object.entries(breakdown.components).map(([key, comp]) => `
                        <tr>
                            <td>
                                <strong>${formatFactorName(key)}</strong>
                                <div class="breakdown-formula">${comp.formula}</div>
                                <div class="breakdown-norm">${comp.normalization}</div>
                            </td>
                            <td>${(comp.weight * 100).toFixed(0)}%</td>
                            <td>${formatRawValue(key, comp.raw)}</td>
                            <td>${comp.normalized.toFixed(1)}</td>
                            <td>${comp.weighted.toFixed(1)}</td>
                            <td><a href="${comp.sourceUrl}" target="_blank">${comp.source}</a></td>
                        </tr>
                    `).join('')}
                </tbody>
                <tfoot>
                    <tr>
                        <td><strong>Total</strong></td>
                        <td>${(breakdown.totalWeight * 100).toFixed(0)}%</td>
                        <td colspan="2">
                            ${breakdown.totalWeight < 1 ? `<em>Adjusted for ${((1 - breakdown.totalWeight) * 100).toFixed(0)}% missing data</em>` : ''}
                        </td>
                        <td><strong>${breakdown.finalScore}</strong></td>
                        <td></td>
                    </tr>
                </tfoot>
            </table>
        </div>

        <div style="margin-top: 1.5rem;">
            <h3 style="margin-bottom: 0.5rem;">Quick Links</h3>
            <p>
                <a href="https://www.zillow.com/homes/${encodeURIComponent(metro.name.split(',')[0])}_rb/" target="_blank">
                    View on Zillow
                </a> |
                <a href="https://www.realtor.com/realestateandhomes-search/${encodeURIComponent(metro.name.split(',')[0].replace(/\s+/g, '-'))}_${metro.state}" target="_blank">
                    View on Realtor.com
                </a> |
                <a href="https://www.google.com/search?q=${encodeURIComponent(metro.name + ' real estate market')}" target="_blank">
                    Google Search
                </a>
            </p>
        </div>
    `;

    modal.style.display = 'block';
}

// Format factor name for display
function formatFactorName(key) {
    const names = {
        gross_yield: 'Gross Rental Yield',
        population_growth: 'Population Growth',
        job_growth: 'Job Growth',
        rent_growth: 'Rent Growth',
        landlord_score: 'Landlord-Friendliness',
        vacancy_rate: 'Vacancy Rate'
    };
    return names[key] || key;
}

// Format raw value based on factor type
function formatRawValue(key, value) {
    if (key === 'landlord_score') {
        return value + '/10';
    }
    return value.toFixed(2) + '%';
}

// Close modal
function closeModal() {
    document.getElementById('detailModal').style.display = 'none';
}

// Export to Excel (CSV)
function exportToExcel() {
    const headers = [
        'Rank', 'Metro', 'State', 'Market Type', 'Composite Score',
        'Median Price', 'Monthly Rent', 'Gross Yield %', 'Rent Growth YoY %',
        'Population Growth YoY %', 'Job Growth YoY %', 'Vacancy Rate %',
        'Landlord Score', 'Crime Rate (per 100k)', 'Nearest Airport', 'Airport Distance (mi)', 'Population'
    ];

    const rows = filteredMetros.map((m, i) => [
        i + 1,
        `"${m.name}"`,
        m.state,
        m.market_type || '',
        m.composite_score,
        m.median_price,
        m.monthly_rent,
        m.gross_yield,
        m.rent_growth_yoy || '',
        m.pop_growth_yoy || '',
        m.job_growth_yoy || '',
        m.vacancy_rate || '',
        m.landlord_score || '',
        m.crime_rate || '',
        m.nearest_airport || '',
        m.airport_distance_miles || '',
        m.population || ''
    ]);

    const csv = [
        headers.join(','),
        ...rows.map(r => r.join(','))
    ].join('\n');

    // Download
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `real_estate_markets_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});

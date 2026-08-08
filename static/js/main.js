// Global state
let currentTab = 'dashboard';
let itemsData = [];
let dbBundle = null;
let viewMode = 'grid'; // 'grid' or 'table'
let ownedOnlyFilter = true;
let topItemsChartInst = null;
let gradeChartInst = null;
let categoryChartInst = null;
let priceHistoryChartInst = null;
let currentModalItemId = null;

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

async function initApp() {
    setupTabNavigation();
    setupFiltersAndControls();
    setupModalEvents();
    setupExportButton();

    // Load static DB JSON bundle
    await loadStaticDataset();

    // Render initial views
    loadOverviewData();
    loadCategoriesAndGrades();
    loadItemsData();
}

/* ----------------------------------------------------
   Static Dataset Loader (GitHub Pages & Local Server)
---------------------------------------------------- */
async function loadStaticDataset() {
    try {
        const res = await fetch('./data/db.json');
        if (!res.ok) throw new Error('Could not fetch data/db.json');
        dbBundle = await res.json();
        console.log('Loaded static dataset successfully:', dbBundle.metadata);
    } catch (err) {
        console.warn('Failed to load ./data/db.json, falling back to REST API if available:', err);
    }
}

function formatMeso(price) {
    if (!price || price === 0) return "0 메소";
    price = parseInt(price);
    const eok = Math.floor(price / 100000000);
    const remainder = price % 100000000;
    const man = Math.floor(remainder / 10000);
    
    let parts = [];
    if (eok > 0) parts.push(`${eok.toLocaleString()}억`);
    if (man > 0) parts.push(`${man.toLocaleString()}만`);
    
    if (parts.length === 0) return `${price.toLocaleString()} 메소`;
    return parts.join(' ') + ' 메소';
}

/* ----------------------------------------------------
   1. Tab Navigation
---------------------------------------------------- */
function setupTabNavigation() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const tabName = btn.getAttribute('data-tab');
            currentTab = tabName;

            document.querySelectorAll('.tab-content').forEach(content => {
                content.style.display = 'none';
            });
            const targetContent = document.getElementById(`tab-${tabName}`);
            if (targetContent) {
                targetContent.style.display = 'block';
            }

            if (tabName === 'dashboard') {
                loadOverviewData();
            } else if (tabName === 'explorer') {
                renderItemsView();
            } else if (tabName === 'seasons') {
                loadSeasonsData();
            } else if (tabName === 'sales') {
                loadSalesData();
            }
        });
    });
}

/* ----------------------------------------------------
   2. Overview & Charts
---------------------------------------------------- */
function loadOverviewData() {
    if (!dbBundle) return;
    const meta = dbBundle.metadata;

    // Recalculate total value dynamically
    const totalVal = dbBundle.items.reduce((sum, item) => sum + (item.total_val || 0), 0);
    const totalQty = dbBundle.items.reduce((sum, item) => sum + (item.qty || 0), 0);

    document.getElementById('kpiTotalVal').innerText = formatMeso(totalVal);
    document.getElementById('kpiTotalQty').innerText = `${totalQty.toLocaleString()} 개`;
    document.getElementById('kpiSalesRevenue').innerText = meta.formatted_sales_revenue;
    document.getElementById('kpiSeasonRange').innerText = `${meta.min_season} ~ ${meta.max_season} 시즌`;

    document.getElementById('kpiTotalItemsSub').innerText = `${meta.total_items.toLocaleString()}개 품목 중 수집중`;
    document.getElementById('kpiSeasonCountSub').innerText = `총 ${meta.season_count}개 시즌 보유`;
    document.getElementById('kpiSalesCountSub').innerText = `총 ${meta.total_sales_count}건 판매 완료`;

    // Compute Grade Stats
    const gradeMap = {};
    dbBundle.items.forEach(item => {
        const g = item.grade || 'G';
        if (!gradeMap[g]) gradeMap[g] = { grade: g, item_count: 0, total_qty: 0, total_val: 0 };
        gradeMap[g].item_count += 1;
        gradeMap[g].total_qty += item.qty || 0;
        gradeMap[g].total_val += item.total_val || 0;
    });

    const gradeStats = Object.values(gradeMap).map(g => {
        g.formatted_val = formatMeso(g.total_val);
        return g;
    }).sort((a, b) => b.total_val - a.total_val);

    // Compute Category Stats
    const catMap = {};
    dbBundle.items.forEach(item => {
        const c = item.category || '기타';
        if (!catMap[c]) catMap[c] = { category: c, item_count: 0, total_qty: 0, total_val: 0 };
        catMap[c].item_count += 1;
        catMap[c].total_qty += item.qty || 0;
        catMap[c].total_val += item.total_val || 0;
    });

    const categoryStats = Object.values(catMap).map(c => {
        c.formatted_val = formatMeso(c.total_val);
        return c;
    }).sort((a, b) => b.total_val - a.total_val);

    // Top 10 High Value Items
    const topItems = [...dbBundle.items].sort((a, b) => b.total_val - a.total_val).slice(0, 10);

    renderTopItemsChart(topItems);
    renderGradeChart(gradeStats);
    renderCategoryChart(categoryStats);
    renderGradeTable(gradeStats);
}

function renderTopItemsChart(topItems) {
    const ctx = document.getElementById('topItemsChart').getContext('2d');
    if (topItemsChartInst) topItemsChartInst.destroy();

    const labels = topItems.map(item => item.name);
    const values = topItems.map(item => item.total_val / 100000000); // 억 메소

    topItemsChartInst = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '총 추정 가치 (억 메소)',
                data: values,
                backgroundColor: 'rgba(251, 191, 36, 0.75)',
                borderColor: '#fbbf24',
                borderWidth: 1,
                borderRadius: 6
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const raw = topItems[context.dataIndex];
                            return ` 가치: ${raw.formatted_total_val} (${raw.qty}개 × ${raw.formatted_price})`;
                        }
                    }
                }
            },
            scales: {
                x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } },
                y: { grid: { display: false }, ticks: { color: '#f8fafc', font: { weight: 'bold' } } }
            }
        }
    });
}

function renderGradeChart(gradeStats) {
    const ctx = document.getElementById('gradeChart').getContext('2d');
    if (gradeChartInst) gradeChartInst.destroy();

    const nameMap = { 'M': 'Master Label', 'S': 'Special Label', 'C': 'Choice Label', 'G': 'General' };
    const colors = { 'M': '#f59e0b', 'S': '#8b5cf6', 'C': '#10b981', 'G': '#64748b' };

    const labels = gradeStats.map(g => nameMap[g.grade] || g.grade);
    const values = gradeStats.map(g => g.total_val);
    const bgColors = gradeStats.map(g => colors[g.grade] || '#475569');

    gradeChartInst = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: bgColors,
                borderWidth: 2,
                borderColor: '#0f172a'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#cbd5e1', font: { size: 12 } } },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            const stat = gradeStats[ctx.dataIndex];
                            return ` ${nameMap[stat.grade] || stat.grade}: ${stat.formatted_val} (${stat.total_qty}개)`;
                        }
                    }
                }
            }
        }
    });
}

function renderCategoryChart(categoryStats) {
    const ctx = document.getElementById('categoryChart').getContext('2d');
    if (categoryChartInst) categoryChartInst.destroy();

    const topCats = categoryStats.slice(0, 7);
    const labels = topCats.map(c => c.category);
    const values = topCats.map(c => c.total_val / 100000000); // 억 메소

    categoryChartInst = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '가치 (억 메소)',
                data: values,
                backgroundColor: 'rgba(6, 182, 212, 0.75)',
                borderColor: '#06b6d4',
                borderWidth: 1,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            const stat = topCats[ctx.dataIndex];
                            return ` 가치: ${stat.formatted_val} (${stat.total_qty}개)`;
                        }
                    }
                }
            },
            scales: {
                x: { grid: { display: false }, ticks: { color: '#f8fafc' } },
                y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } }
            }
        }
    });
}

function renderGradeTable(gradeStats) {
    const tbody = document.querySelector('#gradeSummaryTable tbody');
    tbody.innerHTML = '';
    const nameMap = { 'M': 'Master Label', 'S': 'Special Label', 'C': 'Choice Label', 'G': 'General' };

    gradeStats.forEach(g => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><span class="grade-badge grade-${g.grade}">${g.grade} (${nameMap[g.grade] || g.grade})</span></td>
            <td>${g.item_count} 개</td>
            <td>${g.total_qty} 개</td>
            <td style="font-weight: 700; color: #fbbf24;">${g.formatted_val}</td>
        `;
        tbody.appendChild(tr);
    });
}

/* ----------------------------------------------------
   3. Item Explorer Filters & View
---------------------------------------------------- */
function loadCategoriesAndGrades() {
    if (!dbBundle) return;

    const catSelect = document.getElementById('filterCategory');
    catSelect.innerHTML = '<option value="">전체 카테고리</option>';
    dbBundle.categories.forEach(cat => {
        catSelect.innerHTML += `<option value="${cat}">${cat}</option>`;
    });

    const seasonSelect = document.getElementById('filterSeason');
    seasonSelect.innerHTML = '<option value="">전체 시즌</option>';
    dbBundle.seasons.forEach(s => {
        seasonSelect.innerHTML += `<option value="${s}">시즌 ${s}</option>`;
    });
}

function loadItemsData() {
    if (!dbBundle) return;

    const q = document.getElementById('searchInput').value.trim().toLowerCase();
    const category = document.getElementById('filterCategory').value;
    const grade = document.getElementById('filterGrade').value;
    const season = document.getElementById('filterSeason').value;
    const sortBy = document.getElementById('sortBy').value;

    let list = [...dbBundle.items];

    if (q) {
        list = list.filter(item => item.name.toLowerCase().includes(q));
    }
    if (category) {
        list = list.filter(item => item.category === category);
    }
    if (grade) {
        list = list.filter(item => item.grade === grade);
    }
    if (ownedOnlyFilter) {
        list = list.filter(item => (item.qty || 0) > 0);
    }
    if (season) {
        const targetSeason = parseInt(season);
        list = list.filter(item => {
            const itemInvs = dbBundle.inventory_by_item[item.id] || [];
            return itemInvs.some(inv => inv.season === targetSeason);
        });
    }

    // Sort
    list.sort((a, b) => {
        if (sortBy === 'total_val') return (b.total_val || 0) - (a.total_val || 0);
        if (sortBy === 'latest_price') return (b.latest_price || 0) - (a.latest_price || 0);
        if (sortBy === 'qty') return (b.qty || 0) - (a.qty || 0);
        if (sortBy === 'name') return a.name.localeCompare(b.name);
        if (sortBy === 'grade') return a.grade.localeCompare(b.grade);
        return 0;
    });

    itemsData = list;
    renderItemsView();
}

function setupFiltersAndControls() {
    const searchInput = document.getElementById('searchInput');
    let debounceTimer;
    searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(loadItemsData, 200);
    });

    document.getElementById('filterCategory').addEventListener('change', loadItemsData);
    document.getElementById('filterGrade').addEventListener('change', loadItemsData);
    document.getElementById('filterSeason').addEventListener('change', loadItemsData);
    document.getElementById('sortBy').addEventListener('change', loadItemsData);

    const btnOwnedOnly = document.getElementById('btnOwnedOnly');
    btnOwnedOnly.addEventListener('click', () => {
        ownedOnlyFilter = !ownedOnlyFilter;
        if (ownedOnlyFilter) {
            btnOwnedOnly.classList.add('active');
            btnOwnedOnly.innerHTML = '<i class="fa-solid fa-check"></i> 보유중만 보기';
        } else {
            btnOwnedOnly.classList.remove('active');
            btnOwnedOnly.innerHTML = '<i class="fa-solid fa-border-all"></i> 전체 아이템 보기';
        }
        loadItemsData();
    });

    const btnViewToggle = document.getElementById('btnViewToggle');
    btnViewToggle.addEventListener('click', () => {
        if (viewMode === 'grid') {
            viewMode = 'table';
            btnViewToggle.innerHTML = '<i class="fa-solid fa-table"></i> 테이블뷰';
        } else {
            viewMode = 'grid';
            btnViewToggle.innerHTML = '<i class="fa-solid fa-border-all"></i> 카드뷰';
        }
        renderItemsView();
    });
}

function renderItemsView() {
    const grid = document.getElementById('itemGrid');
    const tableWrapper = document.getElementById('itemTableWrapper');
    const tbody = document.querySelector('#itemTable tbody');

    grid.innerHTML = '';
    tbody.innerHTML = '';

    if (itemsData.length === 0) {
        grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px; color: #94a3b8;">검색 결과가 없습니다.</div>';
        return;
    }

    if (viewMode === 'grid') {
        grid.style.display = 'grid';
        tableWrapper.style.display = 'none';

        itemsData.forEach(item => {
            const card = document.createElement('div');
            card.className = 'item-card';
            card.onclick = () => openItemModal(item.id);

            card.innerHTML = `
                <div class="card-top">
                    <span class="grade-badge grade-${item.grade}">${item.grade}</span>
                    <span class="category-tag">${item.category}</span>
                </div>
                <div class="item-name">${item.name}</div>
                <div class="item-stats-row">
                    <div class="stat-block">
                        <span class="lbl">최신 시세</span>
                        <span class="val">${item.formatted_price}</span>
                    </div>
                    <div class="stat-block" style="text-align: right;">
                        <span class="lbl">보유 (가치)</span>
                        <span class="qty-val">${item.qty}개 (${item.formatted_total_val})</span>
                    </div>
                </div>
            `;
            grid.appendChild(card);
        });
    } else {
        grid.style.display = 'none';
        tableWrapper.style.display = 'block';

        itemsData.forEach(item => {
            const tr = document.createElement('tr');
            tr.onclick = () => openItemModal(item.id);

            tr.innerHTML = `
                <td><span class="grade-badge grade-${item.grade}">${item.grade}</span></td>
                <td style="font-weight: 700;">${item.name}</td>
                <td>${item.category}</td>
                <td style="color: #06b6d4; font-weight: 600;">${item.qty} 개</td>
                <td style="color: #fbbf24; font-weight: 600;">${item.formatted_price}</td>
                <td style="color: #10b981; font-weight: 700;">${item.formatted_total_val}</td>
                <td style="color: #64748b; font-size: 12px;">${item.latest_price_date || '-'}</td>
            `;
            tbody.appendChild(tr);
        });
    }
}

/* ----------------------------------------------------
   4. Item Detail Modal
---------------------------------------------------- */
function openItemModal(itemId) {
    if (!dbBundle) return;
    const item = dbBundle.items.find(i => i.id === itemId);
    if (!item) return;

    currentModalItemId = itemId;

    document.getElementById('modalItemName').innerText = item.name;
    document.getElementById('modalCategoryTag').innerText = item.category;

    const gradeBadge = document.getElementById('modalGradeBadge');
    gradeBadge.innerText = item.grade;
    gradeBadge.className = `grade-badge grade-${item.grade}`;

    const gradeSelect = document.getElementById('modalGradeSelect');
    if (gradeSelect) gradeSelect.value = item.grade;

    const prices = dbBundle.prices_by_item[itemId] || [];
    const inventory = dbBundle.inventory_by_item[itemId] || [];
    const sales = dbBundle.sales_by_item[itemId] || [];

    document.getElementById('modalLatestPrice').innerText = item.formatted_price;
    document.getElementById('modalTotalQty').innerText = `${item.qty} 개`;
    document.getElementById('modalTotalVal').innerText = item.formatted_total_val;

    // Render Price History Chart
    renderPriceHistoryChart(prices);

    // Render Inventory List
    const invList = document.getElementById('modalInventoryList');
    invList.innerHTML = '';
    if (inventory.length === 0) {
        invList.innerHTML = '<div style="color: #64748b;">보유 내역 없음</div>';
    } else {
        inventory.forEach(inv => {
            invList.innerHTML += `
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <span>시즌 ${inv.season}</span>
                    <span style="font-weight: 700; color: #06b6d4;">${inv.quantity_obtained} 개</span>
                </div>
            `;
        });
    }

    // Render Sales List
    const salesList = document.getElementById('modalSalesList');
    salesList.innerHTML = '';
    if (sales.length === 0) {
        salesList.innerHTML = '<div style="color: #64748b;">판매 기록 없음</div>';
    } else {
        sales.forEach(sale => {
            salesList.innerHTML += `
                <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <span>${sale.sell_date} (${sale.quantity_sold}개)</span>
                    <span style="font-weight: 700; color: #10b981;">${sale.formatted_total_sell_val}</span>
                </div>
            `;
        });
    }

    const modal = document.getElementById('itemModal');
    modal.classList.add('active');
}

function renderPriceHistoryChart(prices) {
    const ctx = document.getElementById('priceHistoryChart').getContext('2d');
    if (priceHistoryChartInst) priceHistoryChartInst.destroy();

    if (!prices || prices.length === 0) return;

    const labels = prices.map(p => p.date);
    const values = prices.map(p => p.price);

    priceHistoryChartInst = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: '시세 (메소)',
                data: values,
                borderColor: '#fbbf24',
                backgroundColor: 'rgba(251, 191, 36, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.3,
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            const raw = prices[ctx.dataIndex];
                            return ` 시세: ${raw.formatted_price}`;
                        }
                    }
                }
            },
            scales: {
                x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } },
                y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } }
            }
        }
    });
}

function setupModalEvents() {
    const modal = document.getElementById('itemModal');
    const closeBtn = document.getElementById('modalCloseBtn');
    closeBtn.addEventListener('click', () => modal.classList.remove('active'));
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('active');
    });

    const gradeSelect = document.getElementById('modalGradeSelect');
    if (gradeSelect) {
        gradeSelect.addEventListener('change', async () => {
            if (!currentModalItemId || !dbBundle) return;
            const newGrade = gradeSelect.value;

            // Update item in local dbBundle
            const targetItem = dbBundle.items.find(i => i.id === currentModalItemId);
            if (targetItem) {
                targetItem.grade = newGrade;

                const gradeBadge = document.getElementById('modalGradeBadge');
                gradeBadge.innerText = newGrade;
                gradeBadge.className = `grade-badge grade-${newGrade}`;
                
                loadOverviewData();
                loadItemsData();
                alert(`✅ [${targetItem.name}] 등급이 ${newGrade}(으)로 변경되었습니다.\n※ 변경사항을 유지하려면 [데이터 내보내기] 탭에서 db.json을 다운로드 후 GitHub에 푸시하세요.`);
            }
        });
    }
}

/* ----------------------------------------------------
   5. Season View
---------------------------------------------------- */
function loadSeasonsData() {
    if (!dbBundle) return;
    const grid = document.getElementById('seasonGrid');
    grid.innerHTML = '';

    dbBundle.seasons_summary.forEach(s => {
        const card = document.createElement('div');
        card.className = 'season-card';
        card.onclick = () => {
            document.getElementById('filterSeason').value = s.season;
            loadItemsData();
            document.querySelector('.tab-btn[data-tab="explorer"]').click();
        };

        card.innerHTML = `
            <div style="font-size: 16px; font-weight: 800; color: #fbbf24; margin-bottom: 8px;">
                <i class="fa-solid fa-calendar-check"></i> 시즌 ${s.season}
            </div>
            <div style="font-size: 13px; color: #94a3b8; margin-bottom: 4px;">보유 품목: ${s.item_count}종</div>
            <div style="font-size: 13px; color: #06b6d4; margin-bottom: 4px;">총 수량: ${s.total_qty}개</div>
            <div style="font-size: 14px; font-weight: 700; color: #10b981; margin-top: 8px;">${s.formatted_val}</div>
        `;
        grid.appendChild(card);
    });
}

/* ----------------------------------------------------
   6. Sales Log View
---------------------------------------------------- */
function loadSalesData() {
    if (!dbBundle) return;
    const tbody = document.querySelector('#salesTable tbody');
    tbody.innerHTML = '';

    dbBundle.sales.forEach(s => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="color: #94a3b8;">${s.sell_date}</td>
            <td style="font-weight: 700; color: #f8fafc;">${s.name}</td>
            <td>${s.category}</td>
            <td><span class="grade-badge grade-${s.grade}">${s.grade}</span></td>
            <td style="color: #06b6d4;">${s.quantity_sold} 개</td>
            <td style="color: #fbbf24;">${s.formatted_price}</td>
            <td style="font-weight: 700; color: #10b981;">${s.formatted_total_sell_val}</td>
        `;
        tbody.appendChild(tr);
    });
}

/* ----------------------------------------------------
   7. Data Entry Form & JSON Exporter
---------------------------------------------------- */

function setupExportButton() {
    const btnExport = document.getElementById('btnExportJson');
    if (!btnExport) return;

    btnExport.addEventListener('click', () => {
        if (!dbBundle) return;
        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(dbBundle, null, 2));
        const downloadAnchor = document.createElement('a');
        downloadAnchor.setAttribute("href", dataStr);
        downloadAnchor.setAttribute("download", "db.json");
        document.body.appendChild(downloadAnchor);
        downloadAnchor.click();
        downloadAnchor.remove();
    });
}

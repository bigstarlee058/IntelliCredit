/* ═══════════════════════════════════════════════════════════════
   INTELLI-CREDIT - Application Logic
   ═══════════════════════════════════════════════════════════════ */

// ── State ──
const state = {
    selectedSample: null,     // "healthy" | "risky" | null
    uploadedFiles: [],
    analysisResults: null,
    pipelineRunning: false,
};

// ── DOM Elements ──
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ═══════════════════════════════════════════════════════════════
//  TAB NAVIGATION
// ═══════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    // Tab switching
    $$('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            $$('.nav-tab').forEach(t => t.classList.remove('active'));
            $$('.tab-panel').forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            $(`#panel-${tabName}`).classList.add('active');
        });
    });

    // File upload handlers
    setupUploadZone();
    setupSampleOptions();
    setupAnalyzeButton();
    setupQualitativeInput();
    setupCAMButtons();
    checkDatabricksStatus();
    setupGlowingEffects();

    // Theme toggle
    const themeToggle = $('#themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            document.body.classList.toggle('light-theme');
            const isLight = document.body.classList.contains('light-theme');
            themeToggle.innerText = isLight ? 'Dark Theme' : 'Light Theme';
        });
    }
});


// ═══════════════════════════════════════════════════════════════
//  FILE UPLOAD
// ═══════════════════════════════════════════════════════════════

function setupUploadZone() {
    const zone = $('#uploadZone');
    const input = $('#fileInput');

    zone.addEventListener('click', () => input.click());
    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('drag-over');
        handleFiles(e.dataTransfer.files);
    });

    input.addEventListener('change', () => {
        handleFiles(input.files);
        input.value = '';
    });
}

function renderFileList() {
    const fileList = $('#fileList');
    fileList.innerHTML = '';
    
    state.uploadedFiles.forEach((file, index) => {
        const size = file.size > 1024 * 1024
            ? `${(file.size / 1024 / 1024).toFixed(1)} MB`
            : `${(file.size / 1024).toFixed(0)} KB`;

        const icon = getFileIcon(file.name);
        const isLargePdf = file.name.toLowerCase().endsWith('.pdf') && file.size > 32 * 1024 * 1024;
        const largeTag = isLargePdf
            ? `<span style="font-size:0.7rem;color:#f59e0b;background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.35);border-radius:4px;padding:2px 6px;margin-left:6px;">⚡ Large — smart key-page extraction will be used</span>`
            : '';
        const el = document.createElement('div');
        el.className = 'file-item';
        el.innerHTML = `
            <span class="file-icon">${icon}</span>
            <span class="file-name">${file.name}${largeTag}</span>
            <span class="file-size">${size}</span>
            <button class="remove-file-btn" data-index="${index}" title="Remove file">✕</button>
        `;
        fileList.appendChild(el);

    });
    
    // Add event listeners to remove buttons
    $$('.remove-file-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent triggering upload zone click
            const idx = parseInt(btn.dataset.index);
            removeFile(idx);
        });
    });
}

function removeFile(index) {
    state.uploadedFiles.splice(index, 1);
    renderFileList();
}

function handleFiles(files) {
    for (const file of files) {
        // Prevent exact duplicates by name
        if (!state.uploadedFiles.some(f => f.name === file.name)) {
            state.uploadedFiles.push(file);
        }
    }
    renderFileList();

    state.selectedSample = null;
    $$('.sample-option').forEach(o => o.classList.remove('selected'));
}

function getFileIcon(name) {
    const ext = name.split('.').pop().toLowerCase();
    const icons = { pdf: '📕', xlsx: '📗', xls: '📗', csv: '📊', docx: '📘', doc: '📘', txt: '📄', json: '📋' };
    return icons[ext] || '📁';
}

// ═══════════════════════════════════════════════════════════════
//  SAMPLE DATA
// ═══════════════════════════════════════════════════════════════

function setupSampleOptions() {
    $('#sampleHealthy').addEventListener('click', () => {
        state.selectedSample = 'healthy';
        $$('.sample-option').forEach(o => o.classList.remove('selected'));
        $('#sampleHealthy').classList.add('selected');
        $('#sampleHealthy').classList.add('selected');
        $('#companyName').value = 'Aravind Industries Pvt Ltd';
        $('#cinNumber').value = '';
        $('#promoterNames').value = 'Rajesh K. Sharma';
    });

    $('#sampleRisky').addEventListener('click', () => {
        state.selectedSample = 'risky';
        $$('.sample-option').forEach(o => o.classList.remove('selected'));
        $('#sampleRisky').classList.add('selected');
        $('#sampleRisky').classList.add('selected');
        $('#companyName').value = 'Global Impex Trading Co.';
        $('#cinNumber').value = '';
        $('#promoterNames').value = 'Vikram Agarwal';
    });

    $('#sampleGrowth').addEventListener('click', () => {
        state.selectedSample = 'growth';
        $$('.sample-option').forEach(o => o.classList.remove('selected'));
        $('#sampleGrowth').classList.add('selected');
        $('#sampleGrowth').classList.add('selected');
        $('#companyName').value = 'Nexus Tech Solutions Pvt Ltd';
        $('#cinNumber').value = '';
        $('#promoterNames').value = 'Aditya Menon';
    });

    $('#sampleStable').addEventListener('click', () => {
        state.selectedSample = 'stable';
        $$('.sample-option').forEach(o => o.classList.remove('selected'));
        $('#sampleStable').classList.add('selected');
        $('#sampleStable').classList.add('selected');
        $('#companyName').value = 'Heritage Retail Marts Ltd';
        $('#cinNumber').value = '';
        $('#promoterNames').value = 'Srinivasan Iyer';
    });
}

// ═══════════════════════════════════════════════════════════════
//  ANALYSIS PIPELINE
// ═══════════════════════════════════════════════════════════════

function setupAnalyzeButton() {
    $('#btnAnalyze').addEventListener('click', runAnalysis);
}

async function runAnalysis() {
    if (state.pipelineRunning) return;

    const companyName = $('#companyName').value.trim();
    const cinNumber = $('#cinNumber').value.trim();
    const promoterNames = $('#promoterNames').value.split(',').map(n => n.trim()).filter(Boolean);
    const useSample = !!state.selectedSample;

    if (!useSample && state.uploadedFiles.length === 0 && !companyName) {
        alert('Please upload documents or select a sample company.');
        return;
    }

    state.pipelineRunning = true;
    $('#btnAnalyze').disabled = true;
    $('#progressSection').classList.remove('hidden');

    // Upload files if any
    if (state.uploadedFiles.length > 0) {
        updateProgress(5, 'Uploading files...');
        const formData = new FormData();
        for (const file of state.uploadedFiles) {
            formData.append('files', file);
        }
        try {
            await fetch('/api/upload', { method: 'POST', body: formData });
        } catch (e) {
            console.error('Upload failed:', e);
        }
    }

    // Start analysis
    updateProgress(10, 'Starting analysis pipeline...');

    try {
        // Start polling for status
        const statusInterval = setInterval(async () => {
            try {
                const resp = await fetch('/api/status');
                const status = await resp.json();
                updateProgress(status.progress, status.step);
            } catch (e) { /* ignore poll errors */ }
        }, 1000);

        const resp = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                company_name: companyName,
                cin_number: cinNumber,
                promoter_names: promoterNames,
                use_sample: useSample,
                sample_type: state.selectedSample || 'healthy',
            }),
        });

        clearInterval(statusInterval);

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.error || 'Analysis failed');
        }

        const results = await resp.json();
        state.analysisResults = results;

        updateProgress(100, 'Analysis complete! ✨');

        // Populate all tabs
        setTimeout(() => {
            populateAnalysis(results);
            populateCreditAnalysis(results);
            populateResearch(results);
            populateScoring(results);
            populateCAM(results);

            // Auto-switch to analysis tab
            $$('.nav-tab').forEach(t => t.classList.remove('active'));
            $$('.tab-panel').forEach(p => p.classList.remove('active'));
            $('#nav-analysis').classList.add('active');
            $('#panel-analysis').classList.add('active');
        }, 800);

    } catch (error) {
        updateProgress(0, `Error: ${error.message}`);
        console.error(error);
    } finally {
        state.pipelineRunning = false;
        $('#btnAnalyze').disabled = false;
    }
}

function updateProgress(pct, text) {
    $('#progressBar').style.width = `${pct}%`;
    $('#progressText').textContent = text;
}

// ═══════════════════════════════════════════════════════════════
//  POPULATE: ANALYSIS TAB
// ═══════════════════════════════════════════════════════════════

function populateAnalysis(results) {
    const ingestion = results.ingestion || {};
    const metrics = ingestion.financial_metrics || {};
    const cv = results.cross_verification || {};

    $('#analysisCompanyName').textContent = ingestion.company_name || 'Company';

    // Metrics grid
    const grid = $('#metricsGrid');
    grid.innerHTML = '';

    const isNBFC = (ingestion.entity_type || metrics.entity_type || '').toLowerCase() === 'nbfc';
    
    // For EBITDA display: use PPOP value as fallback for NBFC, but keep label as EBITDA
    let ebitdaDisplay = metrics.ebitda;
    let ebitdaLabel = 'EBITDA';
    if (isNBFC && (!ebitdaDisplay || ebitdaDisplay.value == null || ebitdaDisplay.value === 'N/A')) {
        if (metrics.ppop && metrics.ppop.value != null) {
            ebitdaDisplay = metrics.ppop;
            ebitdaLabel = 'EBITDA (PPOP)';
        }
    }

    // --- Frontend fallback computations ---
    // PAT: if null, try to compute from revenue and margin_pct
    let patDisplay = metrics.pat;
    if (!patDisplay || patDisplay.value == null || patDisplay.value === 'N/A') {
        const rev = metrics.revenue;
        const patObj = metrics.pat;
        if (patObj && typeof patObj === 'object' && patObj.margin_pct != null && rev && rev.value) {
            const computedPat = +(rev.value * patObj.margin_pct / 100).toFixed(2);
            patDisplay = { value: computedPat, unit: 'Cr', margin_pct: patObj.margin_pct };
        }
    }

    // Net Worth: try multiple fallbacks
    let nwDisplay = metrics.net_worth;
    if (!nwDisplay || (typeof nwDisplay === 'object' && (nwDisplay.value == null || nwDisplay.value === 'N/A' || nwDisplay.value === 0)) ||
        nwDisplay === 'N/A' || nwDisplay === null) {
        // Fallback 1: total_debt / debt_equity_ratio
        const td = metrics.total_debt;
        const de = metrics.debt_equity_ratio;
        const tdVal = td && typeof td === 'object' ? td.value : td;
        if (tdVal && typeof de === 'number' && de > 0) {
            const computedNW = +(tdVal / de).toFixed(2);
            nwDisplay = { value: computedNW, unit: 'Cr' };
        } else {
            // Fallback 2: total_assets - total_debt
            const ta = metrics.total_assets;
            const taVal = ta && typeof ta === 'object' ? ta.value : ta;
            if (taVal && tdVal && typeof taVal === 'number' && typeof tdVal === 'number') {
                const computedNW = +(taVal - tdVal).toFixed(2);
                nwDisplay = { value: computedNW, unit: 'Cr' };
            }
        }
    }

    // D/E Ratio: compute from total_debt and net_worth if not available
    let deRatio = metrics.debt_equity_ratio;
    if (deRatio == null || deRatio === 'N/A' || deRatio === 0) {
        const tdVal = metrics.total_debt && typeof metrics.total_debt === 'object' ? metrics.total_debt.value : metrics.total_debt;
        const nwVal = nwDisplay && typeof nwDisplay === 'object' ? nwDisplay.value : nwDisplay;
        if (tdVal && nwVal && typeof tdVal === 'number' && typeof nwVal === 'number' && nwVal > 0) {
            deRatio = +(tdVal / nwVal).toFixed(2);
        }
    }

    const metricItems = [
        { label: 'Revenue', value: formatMetric(metrics.revenue), change: formatChange(metrics.revenue) },
        { label: ebitdaLabel, value: formatMetric(ebitdaDisplay), change: formatMargin(ebitdaDisplay) },
        { label: 'PAT', value: formatMetric(patDisplay), change: formatMargin(patDisplay) },
        { label: 'Total Debt', value: formatMetric(metrics.total_debt) },
        { label: 'Net Worth', value: formatMetric(nwDisplay) },
        { label: 'D/E Ratio', value: typeof deRatio === 'number' ? deRatio.toFixed(2) + 'x' : deRatio ?? 'N/A' },
        { label: 'Current Ratio', value: typeof metrics.current_ratio === 'number' ? metrics.current_ratio.toFixed(2) : metrics.current_ratio ?? 'N/A' },
        { label: 'DSCR', value: typeof metrics.dscr === 'number' ? metrics.dscr.toFixed(2) : metrics.dscr ?? 'N/A' },
        { label: 'ICR', value: typeof metrics.interest_coverage_ratio === 'number' ? metrics.interest_coverage_ratio.toFixed(2) : metrics.interest_coverage_ratio ?? 'N/A' },
        { label: 'Credit Rating', value: metrics.credit_rating || 'N/A' },
    ];

    metricItems.forEach(m => {
        const card = document.createElement('div');
        card.className = 'metric-card';
        card.innerHTML = `
            <div class="metric-label">${m.label}</div>
            <div class="metric-value">${m.value}</div>
            ${m.change ? `<div class="metric-change ${m.changeClass || ''}">${m.change}</div>` : ''}
        `;
        grid.appendChild(card);
    });

    // Charts - pass enhanced metrics with fallback values
    const chartMetrics = Object.assign({}, metrics, {
        ebitda: ebitdaDisplay,
        pat: patDisplay,
        net_worth: nwDisplay,
    });
    renderFinancialsChart(chartMetrics);
    renderCrossVerifyChart(cv);

    // Cross-verification details
    const cvDetails = $('#crossVerifyDetails');
    cvDetails.innerHTML = '';
    (cv.checks_performed || []).forEach(check => {
        const status = check.discrepancy || check.risk_detected || check.inflation_detected || check.mismatch_detected
            ? (check.severity === 'HIGH' ? 'fail' : 'warning') : 'pass';
        const div = document.createElement('div');
        div.className = `cv-check ${status}`;
        div.innerHTML = `
            <div class="cv-check-name">${check.check_name || 'Check'}</div>
            <div class="cv-check-detail">${check.detail || ''}</div>
        `;
        cvDetails.appendChild(div);
    });
}

function formatMetric(val) {
    if (val === null || val === undefined || val === 'N/A') return 'N/A';
    if (typeof val === 'object') {
        if (val.value === null || val.value === undefined || val.value === 'N/A') return 'N/A';
        return `₹${val.value}${val.unit ? ' ' + val.unit : ''}`;
    }
    return String(val);
}

function formatChange(val) {
    if (val && typeof val === 'object' && val.growth_pct != null) {
        const pct = val.growth_pct;
        return `${pct > 0 ? '↑' : '↓'} ${Math.abs(pct)}%`;
    }
    return null;
}

function formatMargin(val) {
    if (val && typeof val === 'object' && val.margin_pct != null) {
        return `Margin: ${val.margin_pct}%`;
    }
    return null;
}

// ═══════════════════════════════════════════════════════════════
//  POPULATE: RESEARCH TAB
// ═══════════════════════════════════════════════════════════════

function populateResearch(results) {
    const research = results.research || {};
    const findings = research.findings || {};
    const nlp = results.nlp || {};

    // Stats
    const stats = $('#researchStats');
    stats.innerHTML = [
        { icon: '📰', label: 'News', count: (findings.news || []).length },
        { icon: '⚖️', label: 'Legal', count: (findings.legal || []).length },
        { icon: '🏛️', label: 'Sector', count: (findings.sector || []).length },
        { icon: '📋', label: 'Regulatory', count: (findings.regulatory || []).length },
    ].map(s => `
        <div class="stat-badge">
            ${s.icon} <span class="stat-count">${s.count}</span> ${s.label}
        </div>
    `).join('');

    // News feed
    renderResearchFeed('#newsFeed', findings.news || []);
    renderResearchFeed('#legalFeed', findings.legal || []);
    renderResearchFeed('#sectorFeed', [...(findings.sector || []), ...(findings.regulatory || [])]);

    // Sentiment
    const sentGrid = $('#sentimentGrid');
    const sentiment = nlp.news_sentiment || {};
    const risk = nlp.risk_signals || {};

    const fraudHits = risk.fraud_keyword_count || 0;
    const fraudThreshold = risk.fraud_threshold || 10;
    const fraudPct = Math.min((fraudHits / fraudThreshold) * 100, 100);
    const fraudBreached = fraudHits >= fraudThreshold;
    const fraudBarColor = fraudBreached ? '#ef4444' : fraudHits >= fraudThreshold * 0.6 ? '#f59e0b' : '#06d6a0';
    const fraudBadge = fraudBreached
        ? `<div style="margin-top:8px;padding:6px 10px;background:rgba(239,68,68,0.15);border:1px solid #ef4444;border-radius:6px;font-size:0.78rem;font-weight:700;color:#ef4444;">🚨 CRITICAL - Fraud Threshold Breached</div>`
        : `<div style="margin-top:8px;padding:5px 10px;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.4);border-radius:6px;font-size:0.76rem;color:#f59e0b;">🔍 Monitoring — ${fraudHits}/${fraudThreshold} signals to flag Critical</div>`;

    sentGrid.innerHTML = `
        <div class="sentiment-item ${(sentiment.overall_label || '').toLowerCase()}">
            <div class="sentiment-label">Overall Sentiment</div>
            <div class="sentiment-value">${sentiment.overall_label || 'Not Available'}</div>
            <div class="sentiment-detail">Score: ${sentiment.overall_score != null ? sentiment.overall_score.toFixed(3) : 'N/A'}</div>
        </div>
        <div class="sentiment-item ${risk.risk_level === 'CRITICAL' ? 'critical' : risk.risk_level === 'HIGH' ? 'negative' : risk.risk_level === 'MODERATE' ? 'neutral' : risk.risk_level === 'Not Assessed' ? '' : 'positive'}">
            <div class="sentiment-label">Risk Level</div>
            <div class="sentiment-value">${risk.risk_level || 'Not Assessed'}</div>
            <div class="sentiment-detail">Score: ${risk.risk_score != null ? risk.risk_score : 'N/A'}/100 • ${risk.signal_count || 0} signals</div>
        </div>
        <div class="sentiment-item neutral">
            <div class="sentiment-label">Articles Analyzed</div>
            <div class="sentiment-value">${sentiment.article_count || 0}</div>
            <div class="sentiment-detail">+${sentiment.positive_count || 0} / -${sentiment.negative_count || 0}</div>
        </div>
        <div class="sentiment-item ${fraudBreached ? 'critical' : 'neutral'}" style="grid-column: 1 / -1;">
            <div class="sentiment-label">🔎 Fraud Signal Monitor</div>
            <div style="display:flex;align-items:center;gap:10px;margin-top:6px;">
                <div style="flex:1;background:rgba(255,255,255,0.07);border-radius:99px;height:8px;overflow:hidden;">
                    <div style="width:${fraudPct}%;background:${fraudBarColor};height:100%;border-radius:99px;transition:width 0.6s ease;"></div>
                </div>
                <span style="font-size:0.82rem;font-weight:700;color:${fraudBarColor};white-space:nowrap;">${fraudHits} / ${fraudThreshold}</span>
            </div>
            ${fraudBadge}
        </div>
    `;


    // Render MCA Data Panel
    const mcaPanel = $('#mcaFeed');
    const mca = findings.mca_data || {};
    if (Object.keys(mca).length > 0) {
        mcaPanel.style.display = 'block';
        mcaPanel.innerHTML = `
            <div class="mca-card">
                <div class="mca-header">
                    <h4>${mca.company_name}</h4>
                    <span class="mca-status ${mca.status === 'Active' ? 'active' : 'inactive'}">${mca.status}</span>
                </div>
                <div class="mca-grid">
                    <div class="mca-item">
                        <span class="mca-label">CIN:</span>
                        <span class="mca-value">${mca.cin}</span>
                    </div>
                    <div class="mca-item">
                        <span class="mca-label">Incorporation:</span>
                        <span class="mca-value">${mca.incorporation_date}</span>
                    </div>
                </div>
                <div class="mca-list">
                    <strong>Directors:</strong>
                    <ul>${(mca.directors || []).map(d => `<li>• ${d}</li>`).join('')}</ul>
                </div>
                <div class="mca-list">
                    <strong>Active Charges:</strong>
                    <ul>${(mca.active_charges || []).map(c => `<li>• ${c.amount} (${c.holder}) - ${c.date}</li>`).join('') || '<li>No active charges found</li>'}</ul>
                </div>
            </div>
        `;
    } else {
        mcaPanel.style.display = 'none';
    }
}

function renderResearchFeed(selector, items) {
    const el = document.querySelector(selector);
    if (!items.length) {
        el.innerHTML = '<p style="color: var(--text-muted); font-size: 0.85rem; padding: 16px;">No findings available. Run analysis to populate.</p>';
        return;
    }
    el.innerHTML = items.slice(0, 15).map(item => `
        <div class="research-item">
            <div class="research-item-title">
                ${item.url ? `<a href="${item.url}" target="_blank" style="color: inherit; text-decoration: underline;">${item.title || 'Untitled'}</a>` : (item.title || 'Untitled')}
            </div>
            <div class="research-item-snippet">${(item.snippet || '').slice(0, 200)}${(item.snippet || '').length > 200 ? '...' : ''}</div>
            <div class="research-item-source">
                ${item.source || ''} ${item.url ? `• <a href="${item.url}" target="_blank">Open →</a>` : ''}
            </div>
        </div>
    `).join('');
}

// ═══════════════════════════════════════════════════════════════
//  POPULATE: SCORING TAB
// ═══════════════════════════════════════════════════════════════

function populateScoring(results) {
    const scoring = results.scoring || {};
    const ml = results.ml_prediction || {};

    // Hero score
    const overall = scoring.overall_score || 0;
    const rec = scoring.recommendation || {};
    const grade = scoring.risk_grade || '';
    const decision = (rec.decision || 'REFER').toUpperCase();

    let scoreClass = overall >= 80 ? 'excellent' : overall >= 60 ? 'good' : overall >= 40 ? 'fair' : 'poor';
    let decClass = decision === 'APPROVE' ? 'approve' : decision === 'REJECT' ? 'reject' : 'refer';

    $('#scoringHero').innerHTML = `
        <div class="score-big ${scoreClass}">${overall.toFixed(1)}</div>
        <div class="score-label">Overall Credit Score</div>
        <div class="score-grade">${grade}</div>
        <div class="score-decision ${decClass}">${decision}</div>
        <div style="margin-top: 12px; color: var(--text-secondary); font-size: 0.85rem;">
            Interest Rate: ${rec.interest_rate_pct || 'N/A'}% p.a. • Risk Premium: ${rec.risk_premium_bps || 'N/A'} bps
        </div>
        ${ml.prediction ? `
        <div style="margin-top: 8px; color: var(--text-muted); font-size: 0.8rem;">
            ML Prediction: ${ml.prediction} (Confidence: ${(ml.confidence * 100).toFixed(1)}%)
        </div>` : ''}
    `;

    // Radar chart
    renderRadarChart(scoring.scores || {});

    // SHAP chart
    renderShapChart(ml.explanation || {});

    // Five Cs details
    const details = $('#fiveCsDetails');
    details.innerHTML = '';
    const scores = scoring.scores || {};
    const detailData = scoring.details || {};

    const formulas = {
        'Capacity': 'Capacity Score = f(Revenue Growth, DSCR, ICR)',
        'Capital': 'Capital Score = f(D/E Ratio, Net Worth)',
        'Character': 'Character Score = f(Litigation + News sentiment + Promoter checks)',
        'Collateral': 'Collateral Score = f(Tangible Net Worth, Total Debt)',
        'Conditions': 'Conditions Score = f(Sector Risk, Regulatory Risk, Macro headwinds)'
    };

    Object.keys(scores).forEach(c => {
        const s = scores[c];
        const d = detailData[c] || {};
        const colorClass = s >= 70 ? 'high' : s >= 50 ? 'mid' : 'low';
        const barColor = s >= 70 ? 'var(--color-success)' : s >= 50 ? 'var(--color-warning)' : 'var(--color-danger)';

        const card = document.createElement('div');
        card.className = 'five-c-card';
        card.innerHTML = `
            <div class="five-c-header">
                <span class="five-c-name">${c}</span>
                <span class="five-c-score ${colorClass}">${s.toFixed(0)}/100</span>
            </div>
            <div class="five-c-bar">
                <div class="five-c-bar-fill" style="width: ${s}%; background: ${barColor};"></div>
            </div>
            <div style="font-size: 0.65rem; color: var(--text-muted); margin-top: 4px; font-style: italic;">
                ${formulas[c] || ''}
            </div>
            <ul class="five-c-factors" style="margin-top: 8px;">
                ${(d.factors || []).map(f => `<li class="five-c-factor">${f}</li>`).join('')}
            </ul>
        `;
        details.appendChild(card);
    });

    // Early Warning Signals (EWS)
    const ewsContainer = $('#ewsFeed');
    if (ewsContainer) {
        const ewsList = scoring.early_warning_signals || [];
        if (!ewsList.length) {
            ewsContainer.innerHTML = '<p style="color: var(--text-muted); font-size: 0.85rem; padding: 16px;">No early warning signals detected.</p>';
        } else {
            ewsContainer.innerHTML = ewsList.map(sig => `
                <div class="cv-check fail" style="margin-bottom: 8px;">
                    <div class="cv-check-name" style="color: var(--color-danger);">⚠️ ${sig.title}</div>
                    <div class="cv-check-detail">${sig.detail}</div>
                </div>
            `).join('');
        }
    }
}

// ═══════════════════════════════════════════════════════════════
//  POPULATE: CAM TAB
// ═══════════════════════════════════════════════════════════════

function populateCAM(results) {
    const ingestion = results.ingestion || {};
    const scoring = results.scoring || {};
    const narrative = results.narrative || {};
    const research = results.research || {};
    const nlp = results.nlp || {};
    
    const rec = scoring.recommendation || {};
    const decision = (rec.decision || 'REFER').toUpperCase();
    const decClass = decision === 'APPROVE' ? 'approve' : decision === 'REJECT' ? 'reject' : 'refer';
    const decColor = decision === 'APPROVE' ? 'var(--color-success)' : decision === 'REJECT' ? 'var(--color-danger)' : 'var(--color-warning)';

    // Heading
    $('#camCompanyName').textContent = ingestion.company_name || 'Company';
    $('#camDate').textContent = new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });

    // 1. Executive Summary
    $('#camExecSummary').textContent = narrative.executive_summary ||
        `Credit appraisal for ${ingestion.company_name || 'the company'} completed. ` +
        `Overall score: ${(scoring.overall_score || 0).toFixed(1)}/100 (${scoring.risk_grade || 'N/A'}). ` +
        `Recommendation: ${decision}.`;

    // 2. Financial Profile
    const fm = ingestion.financial_metrics || {};
    const getVal = (m) => m ? (m.value !== undefined ? m.value : m) : 'N/A';
    $('#camFinancials').innerHTML = `
        <table style="width: 100%; border-collapse: collapse; text-align: left;">
            <tr style="border-bottom: 1px solid var(--border-glass);"><th style="padding: 6px 0;">Revenue</th><td style="text-align: right; font-family: 'JetBrains Mono', monospace;">₹${getVal(fm.revenue)} Cr</td></tr>
            <tr style="border-bottom: 1px solid var(--border-glass);"><th style="padding: 6px 0;">PAT</th><td style="text-align: right; font-family: 'JetBrains Mono', monospace;">₹${getVal(fm.pat)} Cr</td></tr>
            <tr style="border-bottom: 1px solid var(--border-glass);"><th style="padding: 6px 0;">Net Worth</th><td style="text-align: right; font-family: 'JetBrains Mono', monospace;">₹${getVal(fm.net_worth)} Cr</td></tr>
            <tr style="border-bottom: 1px solid var(--border-glass);"><th style="padding: 6px 0;">Total Debt</th><td style="text-align: right; font-family: 'JetBrains Mono', monospace;">₹${getVal(fm.total_debt)} Cr</td></tr>
            <tr><th style="padding: 6px 0;">Debt/Equity</th><td style="text-align: right; font-family: 'JetBrains Mono', monospace;">${getVal(fm.debt_equity_ratio)}x</td></tr>
        </table>
    `;

    // 3. Risks & Intelligence
    const ews_count = (nlp.early_warning_signals || []).length;
    const r_findings = research.findings || {};
    let riskHtml = `
        <div style="margin-bottom: 8px;"><strong>NLP Sentiment:</strong> <span style="color: ${nlp.overall_sentiment === 'POSITIVE' ? 'var(--color-success)' : nlp.overall_sentiment === 'NEGATIVE' ? 'var(--color-danger)' : 'var(--text-primary)'}">${nlp.overall_sentiment || 'NEUTRAL'}</span></div>
        <div style="margin-bottom: 8px;"><strong>Early Warnings:</strong> <span style="color: ${ews_count > 0 ? 'var(--color-danger)' : 'var(--color-success)'}">${ews_count} Flags Detected</span></div>
        <div style="margin-bottom: 8px;"><strong>News Highlights:</strong> ${(r_findings.news || []).length} articles scanned</div>
        <div><strong>Regulatory Hits:</strong> ${(r_findings.regulatory || []).length} / <strong>Legal Hits:</strong> ${(r_findings.legal || []).length}</div>
    `;
    $('#camRisks').innerHTML = riskHtml;

    // 4. Qualitative Narrative & 5 Cs
    const fiveC = narrative.five_cs_narrative || {};
    $('#camNarrative').innerHTML = `
        ${narrative.company_overview ? `<p style="margin-bottom: 12px;"><strong>Overview:</strong> ${narrative.company_overview}</p>` : ''}
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 0.8rem;">
            <div><strong>Character:</strong> ${fiveC.character || 'N/A'}</div>
            <div><strong>Capacity:</strong> ${fiveC.capacity || 'N/A'}</div>
            <div><strong>Capital:</strong> ${fiveC.capital || 'N/A'}</div>
            <div><strong>Collateral:</strong> ${fiveC.collateral || 'N/A'}</div>
        </div>
        ${narrative.risk_assessment ? `<p style="margin-top: 12px; color: var(--color-danger);"><strong>Risk:</strong> ${narrative.risk_assessment}</p>` : ''}
    `;

    // 5. Final Recommendation
    $('#camRecommendation').innerHTML = `
        <div style="padding: 24px; background: rgba(${decision === 'APPROVE' ? '6,214,160' : decision === 'REJECT' ? '239,68,68' : '245,158,11'}, 0.1); border: 2px solid ${decColor}; border-radius: 12px;">
            <div style="font-size: 2rem; font-weight: 900; color: ${decColor}; margin-bottom: 8px;">${decision}</div>
            <div style="color: var(--text-secondary); font-size: 0.9rem;">
                Interest Rate: ${rec.interest_rate_pct || 'N/A'}% p.a.<br>
                Risk Premium: ${rec.risk_premium_bps || 'N/A'} basis points<br>
                Score: ${(scoring.overall_score || 0).toFixed(1)}/100 • ${scoring.risk_grade || ''}
            </div>
            ${rec.key_reasons && rec.key_reasons.length > 0 ? `
            <div style="margin-top: 12px; text-align: left; color: var(--text-secondary); font-size: 0.82rem;">
                <strong>Key Factors:</strong>
                <ul style="margin-top: 6px; padding-left: 20px;">
                    ${rec.key_reasons.map(r => `<li>${r}</li>`).join('')}
                </ul>
            </div>` : ''}
        </div>
    `;
}

// ═══════════════════════════════════════════════════════════════
//  POPULATE: CREDIT ANALYSIS TAB
// ═══════════════════════════════════════════════════════════════

function populateCreditAnalysis(results) {
    const ca = results.credit_analysis;
    if (!ca) return;

    // Show error banner if backend reported an error
    if (ca.error) {
        $('#entityClassContent').innerHTML = `
            <div style="color: var(--color-danger); background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.3); border-radius: 8px; padding: 14px; width: 100%;">
                <strong>⚠️ Credit Analysis Error:</strong> ${ca.error}
                <br><span style="font-size: 0.78rem; color: var(--text-muted);">Check server logs for full traceback. Financial data may be incomplete.</span>
            </div>`;
        return;
    }

    // --- Step 1: Entity Classification ---
    const ec = ca.entity_classification || {};
    const entityEl = $('#entityClassContent');
    const isNBFC = ec.entity_type === 'NBFC';
    entityEl.innerHTML = `
        <span class="entity-badge ${isNBFC ? 'nbfc' : 'corporate'}">
            ${isNBFC ? '🏦' : '🏢'} ${ec.entity_type || 'Unknown'}
        </span>
        <span style="color: var(--text-secondary); font-size: 0.9rem;">${ec.description || ''}</span>
    `;

    // --- Step 2: Financial Inputs ---
    const inputs = ca.financial_inputs || {};
    const common = inputs.common || {};
    const nbfc = inputs.nbfc || {};
    const inputsBody = $('#financialInputsBody');
    const inputLabels = {
        total_revenue: 'Total Revenue / Sales',
        ebitda: 'EBITDA',
        ebit: 'EBIT',
        net_profit_pat: 'Net Profit (PAT)',
        total_debt: 'Total Debt',
        net_worth: 'Net Worth',
        current_assets: 'Current Assets',
        current_liabilities: 'Current Liabilities',
        operating_cash_flow: 'Operating Cash Flow',
        interest_expense: 'Interest Expense',
    };
    const nbfcLabels = {
        loan_book_aum: 'Loan Book (AUM)',
        nii: 'Net Interest Income (NII)',
        nim_pct: 'Net Interest Margin (NIM) %',
        gnpa_pct: 'Gross NPA %',
        nnpa_pct: 'Net NPA %',
        car_pct: 'Capital Adequacy Ratio (CAR) %',
        cost_of_funds_pct: 'Cost of Funds %',
        roa_pct: 'Return on Assets (ROA) %',
        roe_pct: 'Return on Equity (ROE) %',
    };

    let inputsHTML = '';
    for (const [key, label] of Object.entries(inputLabels)) {
        const val = common[key];
        const displayVal = val === 'Not Available' ? '<span style="color: var(--text-muted); font-style: italic;">Not Available</span>'
            : (typeof val === 'number' ? `₹ ${val.toLocaleString('en-IN')} Cr` : val);
        inputsHTML += `<tr><td style="font-weight: 500;">${label}</td><td style="font-family: 'JetBrains Mono', monospace;">${displayVal}</td></tr>`;
    }
    if (isNBFC) {
        inputsHTML += '<tr><td colspan="2" style="padding-top: 16px; font-weight: 700; color: var(--color-purple);">NBFC-Specific Metrics</td></tr>';
        for (const [key, label] of Object.entries(nbfcLabels)) {
            const val = nbfc[key];
            const displayVal = val === 'Not Available' ? '<span style="color: var(--text-muted); font-style: italic;">Not Available</span>'
                : (typeof val === 'number' ? (key.includes('pct') ? `${val}%` : `₹ ${val.toLocaleString('en-IN')} Cr`) : val);
            inputsHTML += `<tr><td style="font-weight: 500;">${label}</td><td style="font-family: 'JetBrains Mono', monospace;">${displayVal}</td></tr>`;
        }
    }
    inputsBody.innerHTML = inputsHTML;

    // --- Step 3: Credit Ratios ---
    const ratios = ca.credit_ratios || [];
    const ratiosBody = $('#creditRatiosBody');
    if (ratios.length) {
        ratiosBody.innerHTML = ratios.map(r => {
            const valDisplay = r.display || (r.value === 'N/A' ? '<span style="color: var(--text-muted);">N/A</span>' : r.value);
            return `<tr>
                <td style="font-weight: 600;">${r.name}</td>
                <td style="font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: var(--text-muted);">${r.formula}</td>
                <td style="font-family: 'JetBrains Mono', monospace; font-weight: 700;">${valDisplay}</td>
                <td style="font-size: 0.82rem; color: var(--text-secondary);">${r.interpretation}</td>
            </tr>`;
        }).join('');
    }

    // --- Step 4: Credit Score ---
    const scoring = ca.credit_scoring || {};
    const finalScore = scoring.final_score || 0;
    const rating = scoring.rating || 'N/A';
    const ratingClass = {
        'AAA': 'score-aaa', 'AA': 'score-aa', 'A': 'score-a',
        'BBB': 'score-bbb', 'BB': 'score-bb', 'High Risk': 'score-high-risk',
    }[rating] || '';

    $('#creditScoreGauge').textContent = finalScore.toFixed(1);
    $('#creditScoreGauge').className = ratingClass;
    $('#creditScoreGauge').style.fontSize = '4rem';
    $('#creditScoreGauge').style.fontWeight = '800';
    $('#creditScoreRating').innerHTML = `<span class="${ratingClass}" style="font-size: 1.5rem; font-weight: 800;">${rating}</span>`;

    const breakdown = scoring.breakdown || [];
    if (breakdown.length) {
        $('#creditScoreBody').innerHTML = breakdown.map(b => {
            const barColor = b.component_score >= 70 ? 'var(--color-success)' : b.component_score >= 50 ? 'var(--color-warning)' : 'var(--color-danger)';
            return `<tr>
                <td style="font-weight: 600;">${b.factor}</td>
                <td style="font-family: 'JetBrains Mono', monospace;">${b.weight}%</td>
                <td style="font-family: 'JetBrains Mono', monospace;">${b.raw_value ?? 'N/A'}</td>
                <td><span style="color: ${barColor}; font-weight: 700;">${b.component_score}</span>/100</td>
                <td style="font-family: 'JetBrains Mono', monospace; font-weight: 700;">${b.weighted_contribution}</td>
            </tr>`;
        }).join('');
    }

    // --- Step 5: Anomaly Flags ---
    const anomalies = ca.anomaly_flags || [];
    const flagsEl = $('#anomalyFlagsContent');
    if (anomalies.length === 0) {
        flagsEl.innerHTML = '<div class="no-flags">✅ No anomaly flags triggered - healthy financial profile.</div>';
    } else {
        flagsEl.innerHTML = anomalies.map(a => `
            <div class="anomaly-item">
                <div class="anomaly-item-title">${a.flag}</div>
                <div class="anomaly-item-condition">${a.condition}</div>
                <div class="anomaly-item-explanation">${a.explanation}</div>
            </div>
        `).join('');
    }
}

// ═══════════════════════════════════════════════════════════════
//  CHARTS
// ═══════════════════════════════════════════════════════════════

let chartFinancials = null;
let chartCrossVerify = null;
let chartRadar = null;
let chartShap = null;

function renderFinancialsChart(metrics) {
    const ctx = document.getElementById('chartFinancials');
    if (chartFinancials) chartFinancials.destroy();

    const labels = ['Revenue', 'EBITDA', 'PAT', 'Net Worth', 'Total Debt'];
    const values = [
        getMetricValue(metrics.revenue),
        getMetricValue(metrics.ebitda),
        getMetricValue(metrics.pat),
        getMetricValue(metrics.net_worth),
        getMetricValue(metrics.total_debt),
    ];

    chartFinancials = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: '₹ Crores',
                data: values,
                backgroundColor: [
                    'rgba(6, 214, 160, 0.7)',
                    'rgba(17, 138, 178, 0.7)',
                    'rgba(99, 102, 241, 0.7)',
                    'rgba(34, 197, 94, 0.7)',
                    'rgba(239, 68, 68, 0.7)',
                ],
                borderRadius: 8,
                borderSkipped: false,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
            },
            scales: {
                y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
                x: { grid: { display: false }, ticks: { color: '#94a3b8' } },
            },
        },
    });
}

function renderCrossVerifyChart(cv) {
    const ctx = document.getElementById('chartCrossVerify');
    if (chartCrossVerify) chartCrossVerify.destroy();

    const score = cv.reconciliation_score || 0;
    const remaining = 100 - score;

    chartCrossVerify = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Score', 'Gap'],
            datasets: [{
                data: [score, remaining],
                backgroundColor: [
                    score >= 70 ? 'rgba(6, 214, 160, 0.8)' : score >= 40 ? 'rgba(245, 158, 11, 0.8)' : 'rgba(239, 68, 68, 0.8)',
                    'rgba(255, 255, 255, 0.05)',
                ],
                borderWidth: 0,
                cutout: '75%',
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false },
            },
        },
        plugins: [{
            id: 'centerText',
            beforeDraw: (chart) => {
                const { ctx, width, height } = chart;
                ctx.save();
                ctx.font = 'bold 32px JetBrains Mono, monospace';
                ctx.fillStyle = '#f1f5f9';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(`${score}`, width / 2, height / 2 - 10);
                ctx.font = '12px Inter, sans-serif';
                ctx.fillStyle = '#94a3b8';
                ctx.fillText('Reconciliation', width / 2, height / 2 + 18);
                ctx.restore();
            },
        }],
    });
}

function renderRadarChart(scores) {
    const ctx = document.getElementById('chartRadar');
    if (chartRadar) chartRadar.destroy();

    const labels = Object.keys(scores).map(s => s.charAt(0).toUpperCase() + s.slice(1));
    const values = Object.values(scores);

    chartRadar = new Chart(ctx, {
        type: 'radar',
        data: {
            labels,
            datasets: [{
                label: 'Score',
                data: values,
                backgroundColor: 'rgba(6, 214, 160, 0.15)',
                borderColor: 'rgba(6, 214, 160, 0.8)',
                borderWidth: 2,
                pointBackgroundColor: 'rgba(6, 214, 160, 1)',
                pointRadius: 5,
                pointHoverRadius: 7,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    grid: { color: 'rgba(255,255,255,0.06)' },
                    angleLines: { color: 'rgba(255,255,255,0.06)' },
                    ticks: { display: false },
                    pointLabels: { color: '#94a3b8', font: { size: 13, weight: '600' } },
                },
            },
            plugins: {
                legend: { display: false },
            },
        },
    });
}

function renderShapChart(explanation) {
    const ctx = document.getElementById('chartShap');
    if (chartShap) chartShap.destroy();

    const importances = (explanation.feature_importances || []).slice(0, 8);
    if (!importances.length) {
        chartShap = new Chart(ctx, {
            type: 'bar',
            data: { labels: ['N/A'], datasets: [{ data: [0], backgroundColor: '#333' }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
        });
        return;
    }

    chartShap = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: importances.map(i => i.feature.replace(/_/g, ' ')),
            datasets: [{
                label: 'SHAP Value',
                data: importances.map(i => i.shap_value),
                backgroundColor: importances.map(i =>
                    i.shap_value > 0 ? 'rgba(239, 68, 68, 0.7)' : 'rgba(6, 214, 160, 0.7)'
                ),
                borderRadius: 6,
                borderSkipped: false,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        afterLabel: (ctx) => {
                            const imp = importances[ctx.dataIndex];
                            if (!imp) return '';
                            return `Feature value: ${imp.feature_value || 'N/A'}\n${imp.direction || ''}`;
                        },
                    },
                },
            },
            scales: {
                x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
                y: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 11 } } },
            },
        },
    });
}

function getMetricValue(val) {
    if (val === null || val === undefined || val === 'N/A') return 0;
    if (typeof val === 'object') {
        if (val.value === null || val.value === undefined || val.value === 'N/A') return 0;
        return val.value;
    }
    return Number(val) || 0;
}

// ═══════════════════════════════════════════════════════════════
//  QUALITATIVE INPUT
// ═══════════════════════════════════════════════════════════════

function setupQualitativeInput() {
    $('#btnQualSubmit').addEventListener('click', async () => {
        const notes = $('#qualNotes').value.trim();
        const category = $('#qualCategory').value;
        const officer = $('#qualOfficer').value.trim();

        if (!notes) { alert('Please enter observations.'); return; }

        $('#btnQualSubmit').disabled = true;
        $('#btnQualSubmit').textContent = 'Analyzing...';

        try {
            const resp = await fetch('/api/qualitative-input', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ notes, category, officer_name: officer }),
            });
            const result = await resp.json();

            const resultEl = $('#qualResult');
            resultEl.classList.remove('hidden');

            const analysis = result.ai_analysis || {};
            resultEl.innerHTML = `
                <h4 style="margin-bottom: 8px; color: var(--text-primary);">AI Analysis</h4>
                <p style="color: var(--text-secondary); font-size: 0.85rem;">${analysis.adjustment_rationale || 'Analysis complete.'}</p>
                <div style="margin-top: 12px; display: flex; gap: 16px;">
                    <div class="stat-badge">
                        Score Adjustment: <span class="stat-count" style="color: ${(analysis.score_adjustment || 0) >= 0 ? 'var(--color-success)' : 'var(--color-danger)'}">${(analysis.score_adjustment || 0) >= 0 ? '+' : ''}${analysis.score_adjustment || 0}</span>
                    </div>
                    <div class="stat-badge">
                        Adjusted Score: <span class="stat-count">${analysis.adjusted_score || 'N/A'}</span>
                    </div>
                </div>
            `;
        } catch (err) {
            alert('Error: ' + err.message);
        } finally {
            $('#btnQualSubmit').disabled = false;
            $('#btnQualSubmit').innerHTML = '<span class="btn-icon">📝</span> Submit & Adjust Score';
        }
    });
}

// ═══════════════════════════════════════════════════════════════
//  CAM GENERATION
// ═══════════════════════════════════════════════════════════════

function setupCAMButtons() {
    $('#btnGenWord').addEventListener('click', () => generateCAM('word'));
    $('#btnGenPdf').addEventListener('click', () => generateCAM('pdf'));
}

async function generateCAM(format) {
    const btn = format === 'word' ? $('#btnGenWord') : $('#btnGenPdf');
    btn.disabled = true;
    btn.textContent = 'Generating...';

    try {
        const resp = await fetch('/api/generate-cam', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ format }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.error || 'CAM generation failed');
        }

        const result = await resp.json();

        $('#camDownload').classList.remove('hidden');
        $('#camDownloadLink').href = `/api/download-cam/${result.filename}`;
        $('#camDownloadLink').textContent = `⬇️ Download ${format.toUpperCase()} (${result.filename})`;

    } catch (err) {
        alert('Error generating CAM: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = format === 'word'
            ? '<span class="btn-icon">📄</span> Generate Word Document'
            : '<span class="btn-icon">📑</span> Generate PDF Document';
    }
}

// ═══════════════════════════════════════════════════════════════
//  DATABRICKS STATUS
// ═══════════════════════════════════════════════════════════════

async function checkDatabricksStatus() {
    try {
        const resp = await fetch('/api/databricks-status');
        const status = await resp.json();
        const badge = $('#dbBadge');
        if (status.connected) {
            badge.classList.add('connected');
            badge.querySelector('.db-text').textContent = 'Databricks';
        } else {
            badge.querySelector('.db-text').textContent = 'Local Mode';
        }
    } catch (e) {
        // Ignore
    }
}

// ═══════════════════════════════════════════════════════════════
//  GLOWING EFFECTS
// ═══════════════════════════════════════════════════════════════

function setupGlowingEffects() {
    let mouseX = 0;
    let mouseY = 0;
    const proximity = 64; // px

    document.body.addEventListener('pointermove', (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;
    });

    const lerp = (start, end, factor) => start + (end - start) * factor;

    function animateGlow() {
        // Select all cards that should have the glow effect
        const cards = document.querySelectorAll('.glass-card, .metric-card, .sample-option');

        cards.forEach(card => {
            const rect = card.getBoundingClientRect();
            
            // Check if mouse is near the card
            const isActive = 
                mouseX > rect.left - proximity && 
                mouseX < rect.right + proximity && 
                mouseY > rect.top - proximity && 
                mouseY < rect.bottom + proximity;

            if (isActive) {
                card.classList.add('glow-active');
            } else {
                card.classList.remove('glow-active');
                return; // skip angle calculation if not active
            }

            const centerX = rect.left + rect.width / 2;
            const centerY = rect.top + rect.height / 2;

            // Calculate target angle
            let targetAngle = (180 * Math.atan2(mouseY - centerY, mouseX - centerX)) / Math.PI + 90;

            // Get current angle or default to 0
            let currentAngle = parseFloat(card.getAttribute('data-glow-angle')) || 0;

            // Ensure smooth rotation over the 360 degree boundary
            let angleDiff = targetAngle - currentAngle;
            while (angleDiff > 180) angleDiff -= 360;
            while (angleDiff < -180) angleDiff += 360;

            // Lerp towards the target angle
            currentAngle = lerp(currentAngle, currentAngle + angleDiff, 0.1);
            
            // Save state and update CSS variable
            card.setAttribute('data-glow-angle', currentAngle);
            card.style.setProperty('--glow-angle', currentAngle);
        });

        requestAnimationFrame(animateGlow);
    }

    // Start animation loop
    requestAnimationFrame(animateGlow);
}

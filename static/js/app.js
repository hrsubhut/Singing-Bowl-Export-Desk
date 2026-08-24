/**
 * API 3 – EXPORT Automation System
 * Client-side script handling multi-source search, AI classification, email cross-check verification,
 * PDF catalog upload, automated personalized Gmail campaign outreach, and UI reactivity.
 */

document.addEventListener('DOMContentLoaded', () => {
    initDragAndDrop();
    initCatalogStatusCheck();
});

// Live Workspace & Data Refresh handler
function handleRefreshData(showToast = true) {
    const topBtn = document.getElementById('headerGlobalRefreshBtn');
    if (topBtn) {
        topBtn.style.opacity = '0.6';
        topBtn.disabled = true;
    }

    fetch('/api/refresh-data')
        .then(async (res) => {
            const data = await res.json();
            if (!res.ok || !data.success) {
                throw new Error(data.error || 'Failed to refresh data.');
            }
            return data;
        })
        .then((data) => {
            if (data.buyers) renderAllBuyersTable(data.buyers);
            if (data.sent_logs) renderSentLogsTable(data.sent_logs);
            if (data.stats) updateDashboardStats(data.stats);
            if (data.catalog_name) {
                const chosenSpan = document.getElementById('chosenFileName');
                const catalogPill = document.getElementById('catalogPill');
                const headerPill = document.getElementById('headerCatalogStatus');
                const attachLabel = document.getElementById('attachCatalogLabel');
                if (chosenSpan) chosenSpan.textContent = data.catalog_name;
                if (catalogPill) {
                    catalogPill.textContent = 'Catalog Attached';
                    catalogPill.className = 'status-pill status-ready';
                }
                if (headerPill) headerPill.textContent = data.catalog_name;
                if (attachLabel) attachLabel.textContent = data.catalog_name;
            }
            if (showToast) {
                displayFlashMessage(`Workspace refreshed: ${data.total_leads || 0} leads loaded from CSV database.`, 'info');
            }
        })
        .catch((err) => {
            console.error('Refresh error:', err);
            displayFlashMessage(err.message || 'Failed to refresh data.', 'danger');
        })
        .finally(() => {
            if (topBtn) {
                topBtn.style.opacity = '1';
                topBtn.disabled = false;
            }
        });
}

// Drag and drop PDF upload initialization
function initDragAndDrop() {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('catalogFile');

    if (!dropzone || !fileInput) return;

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, () => dropzone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, () => dropzone.classList.remove('dragover'), false);
    });

    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            fileInput.files = files;
            updateFileName(fileInput);
        }
    });
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function updateFileName(input) {
    const chosenSpan = document.getElementById('chosenFileName');
    if (input.files && input.files.length > 0) {
        chosenSpan.textContent = input.files[0].name;
    } else {
        chosenSpan.textContent = 'No file selected';
    }
}

// Display floating or inline notification flash
function displayFlashMessage(message, type = 'info') {
    let flashContainer = document.querySelector('.flash-messages-container');
    if (!flashContainer) {
        flashContainer = document.createElement('div');
        flashContainer.className = 'flash-messages-container';
        flashContainer.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            max-width: 480px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        `;
        document.body.appendChild(flashContainer);
    }

    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.style.cssText = `
        padding: 12px 18px;
        border-radius: 8px;
        font-size: 0.875rem;
        font-weight: 500;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        background-color: ${type === 'success' ? '#ecfdf5' : type === 'danger' ? '#fef2f2' : type === 'warning' ? '#fffbeb' : '#eff6ff'};
        color: ${type === 'success' ? '#065f46' : type === 'danger' ? '#991b1b' : type === 'warning' ? '#92400e' : '#1e40af'};
        border: 1px solid ${type === 'success' ? '#a7f3d0' : type === 'danger' ? '#fecaca' : type === 'warning' ? '#fde68a' : '#bfdbfe'};
        animation: slideIn 0.25s ease-out;
    `;

    alert.innerHTML = `
        <div style="flex: 1;">${escapeHtml(message)}</div>
        <button type="button" style="background: none; border: none; font-size: 18px; cursor: pointer; color: inherit; line-height: 1;" onclick="this.parentElement.remove()">×</button>
    `;

    flashContainer.appendChild(alert);

    setTimeout(() => {
        if (alert.parentElement) {
            alert.style.opacity = '0';
            alert.style.transition = 'opacity 0.3s ease';
            setTimeout(() => alert.remove(), 300);
        }
    }, 6000);
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Render buyers table
function renderAllBuyersTable(buyers) {
    const tbody = document.getElementById('buyersTableBody');
    if (!tbody) return;

    if (!buyers || buyers.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="8">
                    <div class="empty-state">
                        <p class="empty-text">No buyer leads currently loaded.</p>
                        <span class="empty-subtext">Use the "Search Leads" section above to discover new leads.</span>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = '';
    buyers.forEach(buyer => {
        const tr = document.createElement('tr');
        const classBadge = (buyer.classification === 'BUSINESS') ? 'badge-business' :
                           (buyer.classification === 'INDIVIDUAL') ? 'badge-individual' : 'badge-neutral';

        const emailCell = buyer.email ? `<code>${escapeHtml(buyer.email)}</code>` : '<span class="text-muted">—</span>';
        const websiteCell = buyer.website ? `<a href="${escapeHtml(buyer.website)}" target="_blank" class="table-link">${escapeHtml(buyer.website)}</a>` : '<span class="text-muted">—</span>';
        const countryCell = buyer.country ? `<span class="badge badge-country">${escapeHtml(buyer.country)}</span>` : '<span class="text-muted">—</span>';

        tr.innerHTML = `
            <td class="font-medium">${escapeHtml(buyer.buyer_name || 'Singing Bowl Buyer')}</td>
            <td>${escapeHtml(buyer.company_name || '—')}</td>
            <td>${emailCell}</td>
            <td>${websiteCell}</td>
            <td>${countryCell}</td>
            <td>${escapeHtml(buyer.source_platform || 'Google/Serper')}</td>
            <td><span class="badge ${classBadge}">${escapeHtml(buyer.classification || 'PENDING')}</span></td>
            <td><span class="status-tag status-${(buyer.status || 'new').toLowerCase()}">${escapeHtml(buyer.status || 'NEW')}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

// Render campaign sent logs history table
function renderSentLogsTable(logs) {
    const tbody = document.getElementById('sentLogsTableBody');
    const badge = document.getElementById('sentLogCountBadge');
    if (badge && logs) {
        badge.textContent = `${logs.length} Sent Entries`;
    }
    if (!tbody) return;

    if (!logs || logs.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="6">
                    <div class="empty-state">
                        <p class="empty-text">No campaign emails dispatched yet.</p>
                        <span class="empty-subtext">Dispatched outreach emails will be logged here to guarantee no duplicate contacts.</span>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = '';
    logs.forEach(log => {
        const tr = document.createElement('tr');
        const dateStr = log.sent_at ? log.sent_at.substring(0, 19).replace('T', ' ') : '—';
        const statusClass = (log.status || 'sent').toLowerCase();

        tr.innerHTML = `
            <td><code>${escapeHtml(log.buyer_email || '—')}</code></td>
            <td class="font-medium">${escapeHtml(log.buyer_name || '—')}</td>
            <td>${escapeHtml(log.campaign_name || '—')}</td>
            <td>${escapeHtml(log.catalog_file || '—')}</td>
            <td class="text-muted">${dateStr}</td>
            <td><span class="status-tag status-${statusClass}">${escapeHtml(log.status || 'SENT')}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

// Update dashboard metric cards
function updateDashboardStats(stats) {
    if (!stats) return;
    const totalEl = document.getElementById('metricTotalLeads');
    const contactedEl = document.getElementById('metricContacted');
    const sentEl = document.getElementById('metricEmailsSent');
    const failedEl = document.getElementById('metricFailed');
    const tableBadge = document.getElementById('tableRecordCountBadge');

    if (totalEl && stats.total_leads !== undefined) totalEl.textContent = stats.total_leads;
    if (contactedEl && stats.contacted !== undefined) contactedEl.textContent = stats.contacted;
    if (sentEl && stats.emails_sent !== undefined) sentEl.textContent = stats.emails_sent;
    if (failedEl && stats.failed !== undefined) failedEl.textContent = stats.failed;
    if (tableBadge && stats.total_leads !== undefined) tableBadge.textContent = `${stats.total_leads} Records`;
}

// Check active catalog status on load
function initCatalogStatusCheck() {
    fetch('/api/catalog/status')
        .then(res => res.json())
        .then(data => {
            if (data.exists && data.filename) {
                const chosenSpan = document.getElementById('chosenFileName');
                const catalogPill = document.getElementById('catalogPill');
                const headerPill = document.getElementById('headerCatalogStatus');
                const attachLabel = document.getElementById('attachCatalogLabel');

                if (chosenSpan) chosenSpan.textContent = `${data.filename} (${data.size_kb} KB)`;
                if (catalogPill) {
                    catalogPill.textContent = 'Catalog Attached';
                    catalogPill.className = 'status-pill status-ready';
                }
                if (headerPill) headerPill.textContent = data.filename;
                if (attachLabel) attachLabel.textContent = data.filename;
            }
        })
        .catch(err => console.debug('Catalog check:', err));
}

// Search Leads UI handler calling POST /api/search with multi-source support
function handleSearchLeads(event) {
    event.preventDefault();
    const queryInput = document.getElementById('searchQuery');
    const countryInput = document.getElementById('targetCountry');
    const limitInput = document.getElementById('leadLimit');
    const btn = document.getElementById('searchBtn');

    if (!queryInput || !btn) return;

    const query = queryInput.value.trim();
    const country = countryInput ? countryInput.value.trim() : '';
    const limit = limitInput ? parseInt(limitInput.value, 10) : 25;

    const sourceCheckboxes = document.querySelectorAll('input[name="discoverySource"]:checked');
    const selectedSources = Array.from(sourceCheckboxes).map(cb => cb.value);

    if (!query) {
        displayFlashMessage('Please enter a search query.', 'danger');
        return;
    }

    if (selectedSources.length === 0) {
        displayFlashMessage('Please select at least one buyer discovery source.', 'warning');
        return;
    }

    const originalButtonHtml = btn.innerHTML;
    btn.innerHTML = `<span class="btn-spinner"></span> Searching across ${selectedSources.length} source(s)...`;
    btn.disabled = true;

    // Show dynamic progress box
    const progressContainer = document.getElementById('searchProgressContainer');
    const progressTitle = document.getElementById('searchProgressTitle');
    const progressSub = document.getElementById('searchProgressSub');
    const progressBar = document.getElementById('searchProgressBar');

    if (progressContainer) {
        progressContainer.style.display = 'block';
        if (progressBar) progressBar.style.width = '20%';
        if (progressTitle) progressTitle.textContent = `Searching Across ${selectedSources.length} Source(s)...`;
        if (progressSub) progressSub.textContent = 'Connecting to Google/Serper & B2B directories...';
    }

    let progressStep = 0;
    const progressInterval = setInterval(() => {
        progressStep++;
        if (progressStep === 1) {
            if (progressBar) progressBar.style.width = '45%';
            if (progressSub) progressSub.textContent = 'Extracting wholesale buyer companies & domains...';
        } else if (progressStep === 2) {
            if (progressBar) progressBar.style.width = '70%';
            if (progressSub) progressSub.textContent = 'Crawling public website contact pages (/contact, /about, /wholesale)...';
        } else if (progressStep === 3) {
            if (progressBar) progressBar.style.width = '88%';
            if (progressSub) progressSub.textContent = 'Extracting emails & performing 3-tier deduplication...';
        }
    }, 1800);

    fetch('/api/search', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            query: query,
            country: country,
            limit: limit,
            sources: selectedSources
        })
    })
    .then(async (response) => {
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || `Search failed with status ${response.status}`);
        }
        return data;
    })
    .then((data) => {
        clearInterval(progressInterval);
        if (progressBar) progressBar.style.width = '100%';
        if (progressSub) progressSub.textContent = 'Discovery & enrichment complete!';

        const sourcesSearched = data.sources ? Object.keys(data.sources).length : selectedSources.length;
        const rawResults = data.raw_results !== undefined ? data.raw_results : (data.search_results || 0);
        const uniqueBuyers = data.unique_leads !== undefined ? data.unique_leads : (data.count || 0);
        const newLeads = data.new_leads !== undefined ? data.new_leads : (data.count || 0);
        const emailsFound = data.leads_with_email !== undefined ? data.leads_with_email : (data.emails_found || 0);

        let unavailableSources = [];
        if (data.sources) {
            for (const [src, info] of Object.entries(data.sources)) {
                if (info.status === 'unavailable') {
                    unavailableSources.push(src);
                }
            }
        }

        if (newLeads > 0 || uniqueBuyers > 0) {
            let msg = `Sources searched: ${sourcesSearched} • Raw results: ${rawResults} • Unique buyers: ${uniqueBuyers} • New leads: ${newLeads} • Emails found: ${emailsFound}`;
            if (unavailableSources.length > 0) {
                msg += ` (${unavailableSources.join(', ')}: Unavailable)`;
            }
            displayFlashMessage(msg, 'success');
            if (data.all_buyers) {
                renderAllBuyersTable(data.all_buyers);
            }
            if (typeof data.total_leads === 'number') {
                const totalEl = document.getElementById('metricTotalLeads');
                const tableBadge = document.getElementById('tableRecordCountBadge');
                if (totalEl) totalEl.textContent = data.total_leads;
                if (tableBadge) tableBadge.textContent = `${data.total_leads} Records`;
            }
        } else {
            let msg = `Search completed: ${rawResults} results checked across ${sourcesSearched} source(s), but no new unique leads were added.`;
            if (unavailableSources.length > 0) {
                msg += ` Note: ${unavailableSources.join(', ')} are currently unavailable.`;
            }
            displayFlashMessage(msg, 'info');
        }
    })
    .catch((err) => {
        clearInterval(progressInterval);
        console.error('Lead search error:', err);
        displayFlashMessage(err.message || 'Failed to search leads. Please check your API configuration.', 'danger');
    })
    .finally(() => {
        clearInterval(progressInterval);
        setTimeout(() => {
            if (progressContainer) progressContainer.style.display = 'none';
        }, 1200);
        btn.innerHTML = originalButtonHtml;
        btn.disabled = false;
    });
}

// AI Lead Classification UI handler calling POST /api/classify
function handleClassifyLeads() {
    const btn = document.getElementById('classifyBtn');
    if (!btn) return;

    const originalButtonHtml = btn.innerHTML;
    btn.innerHTML = `<span class="btn-spinner"></span> Classifying with Gemini...`;
    btn.disabled = true;

    fetch('/api/classify', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(async (response) => {
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || `Classification failed with status ${response.status}`);
        }
        return data;
    })
    .then((data) => {
        const count = data.classified_count || 0;
        if (count > 0) {
            displayFlashMessage(`AI classification completed: ${count} lead(s) classified.`, 'success');
            if (data.buyers) {
                renderAllBuyersTable(data.buyers);
            }
        } else {
            displayFlashMessage(data.message || 'No pending leads required classification.', 'info');
        }
    })
    .catch((err) => {
        console.error('Gemini classification error:', err);
        displayFlashMessage(err.message || 'Failed to classify leads with Gemini. Please check your configuration.', 'danger');
    })
    .finally(() => {
        btn.innerHTML = originalButtonHtml;
        btn.disabled = false;
    });
}

// Email Verification & Cross-Checking UI handler calling POST /api/verify-emails
function handleVerifyEmails() {
    const btn = document.getElementById('verifyEmailsBtn');
    if (!btn) return;

    const originalButtonHtml = btn.innerHTML;
    btn.innerHTML = `<span class="btn-spinner"></span> Verifying emails...`;
    btn.disabled = true;

    fetch('/api/verify-emails', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(async (response) => {
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || 'Email verification request failed.');
        }
        return data;
    })
    .then((data) => {
        const verified = data.verified_count || 0;
        const invalid = data.invalid_count || 0;
        const total = data.total_checked || 0;

        displayFlashMessage(`Email cross-check complete: ${verified} verified deliverable, ${invalid} unresolvable/invalid across ${total} records.`, 'success');
    })
    .catch((err) => {
        console.error('Email verification error:', err);
        displayFlashMessage(err.message || 'Failed to verify emails.', 'danger');
    })
    .finally(() => {
        btn.innerHTML = originalButtonHtml;
        btn.disabled = false;
    });
}

// Catalog Upload UI handler calling POST /api/upload-catalog
function handleCatalogUpload(event) {
    event.preventDefault();
    const fileInput = document.getElementById('catalogFile');
    const uploadBtn = document.getElementById('uploadBtn');

    if (!fileInput.files || fileInput.files.length === 0) {
        displayFlashMessage('Please select a PDF catalog file to upload.', 'warning');
        return;
    }

    const file = fileInput.files[0];
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        displayFlashMessage('Only PDF (.pdf) files are supported for export presentation catalogs.', 'danger');
        return;
    }

    const formData = new FormData();
    formData.append('catalog_pdf', file);

    const originalBtnHtml = uploadBtn.innerHTML;
    uploadBtn.innerHTML = `<span class="btn-spinner"></span> Uploading catalog...`;
    uploadBtn.disabled = true;

    fetch('/api/upload-catalog', {
        method: 'POST',
        body: formData
    })
    .then(async (res) => {
        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.error || `Upload failed with status ${res.status}`);
        }
        return data;
    })
    .then((data) => {
        displayFlashMessage(data.message || 'Catalog PDF uploaded successfully!', 'success');

        const chosenSpan = document.getElementById('chosenFileName');
        const catalogPill = document.getElementById('catalogPill');
        const headerPill = document.getElementById('headerCatalogStatus');
        const attachLabel = document.getElementById('attachCatalogLabel');

        if (chosenSpan) chosenSpan.textContent = `${data.filename} (${data.size_kb} KB)`;
        if (catalogPill) {
            catalogPill.textContent = 'Catalog Attached';
            catalogPill.className = 'status-pill status-ready';
        }
        if (headerPill) headerPill.textContent = data.filename;
        if (attachLabel) attachLabel.textContent = data.filename;
    })
    .catch((err) => {
        console.error('Catalog upload error:', err);
        displayFlashMessage(err.message || 'Failed to upload catalog PDF.', 'danger');
    })
    .finally(() => {
        uploadBtn.innerHTML = originalBtnHtml;
        uploadBtn.disabled = false;
    });
}

// Automated Campaign Outreach UI handler calling POST /api/campaign/send
function handleSendCampaign(event) {
    event.preventDefault();
    const audienceSelect = document.getElementById('targetAudience');
    const campaignNameInput = document.getElementById('campaignName');
    const subjectInput = document.getElementById('campaignSubject');
    const bodyInput = document.getElementById('campaignBody');
    const attachCheck = document.getElementById('attachCatalogCheck');
    const btn = document.getElementById('sendCampaignBtn');

    if (!subjectInput || !bodyInput || !btn) return;

    const targetFilter = audienceSelect ? audienceSelect.value : 'BUSINESS_ONLY';
    const campaignName = campaignNameInput ? campaignNameInput.value.trim() : 'Singing Bowl Export Outreach';
    const subject = subjectInput.value.trim();
    const body = bodyInput.value.trim();
    const attachCatalog = attachCheck ? attachCheck.checked : true;

    if (!subject) {
        displayFlashMessage('Please enter an email subject line.', 'danger');
        return;
    }
    if (!body) {
        displayFlashMessage('Please enter an email body template.', 'danger');
        return;
    }

    const originalButtonHtml = btn.innerHTML;
    btn.innerHTML = `<span class="btn-spinner"></span> Dispathing personalized emails via Gmail...`;
    btn.disabled = true;

    fetch('/api/campaign/send', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            target_filter: targetFilter,
            campaign_name: campaignName,
            subject: subject,
            body: body,
            attach_catalog: attachCatalog
        })
    })
    .then(async (response) => {
        const data = await response.json();
        if (!response.ok || !data.success) {
            throw new Error(data.error || `Campaign send failed with status ${response.status}`);
        }
        return data;
    })
    .then((data) => {
        const sent = data.sent || 0;
        const skipped = data.skipped || 0;
        const failed = data.failed || 0;

        let msg = `Campaign completed: ${sent} personalized email(s) sent successfully via Gmail!`;
        if (skipped > 0) msg += ` (${skipped} already contacted / skipped)`;
        if (failed > 0) msg += ` (${failed} delivery issue(s))`;

        displayFlashMessage(msg, sent > 0 ? 'success' : 'warning');

        if (data.stats) updateDashboardStats(data.stats);
        if (data.all_buyers) renderAllBuyersTable(data.all_buyers);
        if (data.all_sent_logs) renderSentLogsTable(data.all_sent_logs);
    })
    .catch((err) => {
        console.error('Campaign send error:', err);
        displayFlashMessage(err.message || 'Failed to dispatch campaign emails.', 'danger');
    })
    .finally(() => {
        btn.innerHTML = originalButtonHtml;
        btn.disabled = false;
    });
}

// Live Email Preview Modal handler calling POST /api/campaign/preview
function handlePreviewEmail() {
    const subjectInput = document.getElementById('campaignSubject');
    const bodyInput = document.getElementById('campaignBody');
    const previewBtn = document.getElementById('previewBtn');

    const subject = subjectInput ? subjectInput.value.trim() : '';
    const body = bodyInput ? bodyInput.value.trim() : '';

    if (previewBtn) previewBtn.disabled = true;

    fetch('/api/campaign/preview', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            subject: subject,
            body: body
        })
    })
    .then(async (res) => {
        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.error || 'Failed to generate email preview.');
        }
        return data;
    })
    .then((data) => {
        const modal = document.getElementById('previewModal');
        const leadNameEl = document.getElementById('previewLeadName');
        const subjectEl = document.getElementById('previewSubjectText');
        const bodyEl = document.getElementById('previewBodyText');
        const attachBadge = document.getElementById('previewAttachmentBadge');

        const buyer = data.sample_buyer || {};
        if (leadNameEl) leadNameEl.textContent = `${buyer.buyer_name || 'Buyer'} (${buyer.company_name || 'Company'}) — ${buyer.country || 'Global'}`;
        if (subjectEl) subjectEl.textContent = data.subject || '—';
        if (bodyEl) bodyEl.textContent = data.body || '—';
        if (attachBadge) {
            attachBadge.textContent = data.catalog_attached ? data.catalog_attached : 'No PDF attached';
            attachBadge.className = data.catalog_attached ? 'badge badge-info' : 'badge badge-neutral';
        }

        if (modal) modal.style.display = 'flex';
    })
    .catch((err) => {
        console.error('Preview error:', err);
        displayFlashMessage(err.message || 'Failed to generate preview.', 'danger');
    })
    .finally(() => {
        if (previewBtn) previewBtn.disabled = false;
    });
}

function closePreviewModal() {
    const modal = document.getElementById('previewModal');
    if (modal) modal.style.display = 'none';
}

// Send Test Email handler calling POST /api/campaign/test-send
function handleSendTestEmail() {
    const subjectInput = document.getElementById('campaignSubject');
    const bodyInput = document.getElementById('campaignBody');
    const attachCheck = document.getElementById('attachCatalogCheck');
    const testBtn = document.getElementById('testSendBtn');

    const subject = subjectInput ? subjectInput.value.trim() : '';
    const body = bodyInput ? bodyInput.value.trim() : '';
    const attachCatalog = attachCheck ? attachCheck.checked : true;

    if (!subject || !body) {
        displayFlashMessage('Please enter an email subject and body template first.', 'warning');
        return;
    }

    const originalBtnHtml = testBtn.innerHTML;
    testBtn.innerHTML = `<span class="btn-spinner"></span> Sending test email...`;
    testBtn.disabled = true;

    fetch('/api/campaign/test-send', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            subject: subject,
            body: body,
            attach_catalog: attachCatalog
        })
    })
    .then(async (res) => {
        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.error || 'Failed to send test email.');
        }
        return data;
    })
    .then((data) => {
        displayFlashMessage(data.message || 'Sample test email dispatched successfully! Please check your Gmail inbox.', 'success');
    })
    .catch((err) => {
        console.error('Test email error:', err);
        displayFlashMessage(err.message || 'Failed to send test email. Please check your Gmail credentials in .env.', 'danger');
    })
    .finally(() => {
        testBtn.innerHTML = originalBtnHtml;
        testBtn.disabled = false;
    });
}


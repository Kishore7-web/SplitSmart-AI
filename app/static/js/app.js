/**
 * SplitSmart AI 2.0 - The Financial Memory of a Group
 * Core Frontend Client Architecture
 */

"use strict";

const API = "";
let allGroups = [];
let currentGroupId = null;
let currentGroupMembers = [];
let currentGroupExpenses = [];
let currentSplitType = "equal";
let selectedUploadFile = null;

// --------------------------------------------------
// 1. UTILITIES & API HELPERS
// --------------------------------------------------

async function apiRequest(url, options = {}) {
    const isFormData = options.body instanceof FormData;
    const headers = {
        ...(options.headers || {})
    };

    if (!isFormData && !headers["Content-Type"]) {
        headers["Content-Type"] = "application/json";
    }

    const response = await fetch(API + url, {
        ...options,
        headers
    });

    let data = {};
    try {
        data = await response.json();
    } catch {
        data = {};
    }

    if (!response.ok) {
        let message = data.detail || "Request failed.";
        if (Array.isArray(message)) {
            message = message.map(item => item.msg || "Invalid input").join(", ");
        }
        throw new Error(message);
    }

    return data;
}

function formatMoney(paise, currency = "INR") {
    const rupees = (Number(paise) || 0) / 100;
    try {
        return new Intl.NumberFormat("en-IN", {
            style: "currency",
            currency: currency || "INR",
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(rupees);
    } catch {
        return `₹${rupees.toFixed(2)}`;
    }
}

function showToast(message, type = "normal") {
    const toast = document.getElementById("toastNotification");
    if (!toast) return;

    toast.textContent = message;
    toast.className = `toast-notification ${type}`;
    toast.classList.remove("hidden");

    setTimeout(() => {
        toast.classList.add("hidden");
    }, 4000);
}

function showMessage(el, text, type = "normal") {
    if (!el) return;
    el.textContent = text;
    if (type === "success") el.style.color = "#10b981";
    else if (type === "error") el.style.color = "#ef4444";
    else el.style.color = "#7c8299";
}

function formatDate(isoStr) {
    if (!isoStr) return "N/A";
    const d = new Date(isoStr);
    return isNaN(d.getTime()) ? isoStr : d.toLocaleDateString("en-IN", {
        month: "short",
        day: "numeric",
        year: "numeric"
    });
}

function formatDateTime(isoStr) {
    if (!isoStr) return "N/A";
    const d = new Date(isoStr);
    return isNaN(d.getTime()) ? isoStr : d.toLocaleString("en-IN", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
}

// --------------------------------------------------
// 2. NAVIGATION & ROUTING
// --------------------------------------------------

function showSection(sectionId) {
    document.querySelectorAll(".page-section").forEach(sec => sec.classList.remove("active"));
    document.querySelectorAll(".sidebar-nav .nav-link").forEach(link => link.classList.remove("active"));

    const targetSec = document.getElementById(sectionId);
    if (targetSec) {
        targetSec.classList.add("active");
    }

    const activeLink = document.querySelector(`.sidebar-nav .nav-link[data-section="${sectionId}"]`);
    if (activeLink) {
        activeLink.classList.add("active");
    }

    const pageHeadings = {
        dashboard: "Dashboard",
        groups: "My Groups & Members",
        timeline: "Activity Timeline",
        expenses: "Expense Management",
        evidence: "Upload & Evidence Centre",
        analytics: "Budget & Analytics",
        settlements: "Settlements",
        paypal: "PayPal Sandbox Payments",
        assistant: "AI Financial Assistant",
        settings: "Settings & Diagnostics"
    };

    const headingEl = document.getElementById("pageHeading");
    if (headingEl && pageHeadings[sectionId]) {
        headingEl.textContent = pageHeadings[sectionId];
    }

    window.location.hash = sectionId;

    // Load section data
    if (currentGroupId) {
        if (sectionId === "timeline") loadTimeline();
        else if (sectionId === "expenses") loadExpenses();
        else if (sectionId === "evidence") loadEvidenceList();
        else if (sectionId === "analytics") loadAnalytics();
        else if (sectionId === "settlements") loadSettlements();
        else if (sectionId === "paypal") loadPayPalModule();
        else if (sectionId === "settings") loadDiagnostics();
    }
}

window.addEventListener("hashchange", () => {
    const hash = window.location.hash.replace("#", "") || "dashboard";
    showSection(hash);
});

// --------------------------------------------------
// 3. GLOBAL GROUP SELECTOR & LIFECYCLE
// --------------------------------------------------

async function initApp() {
    try {
        await loadGroups();
        const initialHash = window.location.hash.replace("#", "") || "dashboard";
        showSection(initialHash);
    } catch (err) {
        console.error("Initialization error:", err);
    }
}

async function loadGroups() {
    const select = document.getElementById("globalGroupSelect");
    try {
        allGroups = await apiRequest("/api/groups/");
        select.innerHTML = "";

        if (allGroups.length === 0) {
            select.innerHTML = '<option value="">No groups created</option>';
            currentGroupId = null;
            updateActiveGroupBadge(null);
            return;
        }

        allGroups.forEach(grp => {
            const opt = document.createElement("option");
            opt.value = grp.id;
            opt.textContent = `${grp.name} · ${grp.activity_type.toUpperCase()}`;
            select.appendChild(opt);
        });

        // Retain current selection or pick first
        if (!currentGroupId || !allGroups.some(g => g.id === Number(currentGroupId))) {
            currentGroupId = allGroups[0].id;
        }

        select.value = currentGroupId;
        const selectedGroup = allGroups.find(g => g.id === Number(currentGroupId));
        updateActiveGroupBadge(selectedGroup);

        await onActiveGroupChanged();
    } catch (err) {
        showToast("Could not load groups: " + err.message, "error");
    }
}

function updateActiveGroupBadge(grp) {
    const badge = document.getElementById("activeGroupBadge");
    const heroLabel = document.getElementById("heroGroupLabel");

    if (!grp) {
        if (badge) badge.textContent = "No group selected";
        if (heroLabel) heroLabel.textContent = "Select a group";
        return;
    }

    const typeStr = (grp.activity_type || "general").toUpperCase();
    const budgetStr = grp.budget_paise > 0 ? ` · Budget: ${formatMoney(grp.budget_paise, grp.currency)}` : "";
    if (badge) badge.textContent = `${typeStr}${budgetStr}`;
    if (heroLabel) heroLabel.textContent = grp.name;
}

async function onGlobalGroupChange(newId) {
    if (!newId) return;
    currentGroupId = Number(newId);
    const selectedGroup = allGroups.find(g => g.id === currentGroupId);
    updateActiveGroupBadge(selectedGroup);
    await onActiveGroupChanged();
}

async function onActiveGroupChanged() {
    if (!currentGroupId) return;

    // Load group members & core data
    await Promise.all([
        loadGroupMembers(),
        loadDashboard()
    ]);

    const activeHash = window.location.hash.replace("#", "") || "dashboard";
    if (activeHash !== "dashboard") {
        showSection(activeHash);
    }
}

async function loadGroupMembers() {
    if (!currentGroupId) return;
    try {
        currentGroupMembers = await apiRequest(`/api/groups/${currentGroupId}/members`);
        renderMembersList();
        populateMemberDropdowns();
    } catch (err) {
        console.error("Failed to load members:", err);
    }
}

function renderMembersList() {
    const container = document.getElementById("membersList");
    if (!container) return;

    container.innerHTML = "";
    if (currentGroupMembers.length === 0) {
        container.innerHTML = '<div class="empty-state">No members in this group yet. Add the first member above.</div>';
        return;
    }

    currentGroupMembers.forEach(m => {
        const item = document.createElement("div");
        item.className = "member-item";

        const left = document.createElement("div");
        left.innerHTML = `
            <strong>${m.name}</strong>
            <span class="status-pill status-${m.role === 'owner' ? 'confirmed' : 'suggested'}" style="margin-left:6px">${m.role.toUpperCase()}</span>
            <br><small style="color:var(--muted)">${m.email || 'No email'} · ${m.phone || 'No phone'}</small>
        `;

        item.appendChild(left);
        container.appendChild(item);
    });
}

function populateMemberDropdowns() {
    const dropdownIds = ["expPayer", "evidenceUploader", "draftPayer"];

    dropdownIds.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;

        const prev = el.value;
        el.innerHTML = '<option value="">Select Member</option>';

        currentGroupMembers.forEach(m => {
            const opt = document.createElement("option");
            opt.value = m.id;
            opt.textContent = `${m.name} (${m.role})`;
            el.appendChild(opt);
        });

        if (prev && currentGroupMembers.some(m => String(m.id) === prev)) {
            el.value = prev;
        } else if (currentGroupMembers.length > 0) {
            el.value = currentGroupMembers[0].id;
        }
    });

    renderParticipantsCheckboxes();
}

// --------------------------------------------------
// 4. DASHBOARD LOGIC
// --------------------------------------------------

async function loadDashboard() {
    const totalGroupsEl = document.getElementById("dashTotalGroups");
    const totalSpentEl = document.getElementById("dashTotalSpent");
    const budgetRemainingEl = document.getElementById("dashBudgetRemaining");
    const budgetPctEl = document.getElementById("dashBudgetPct");
    const pendingSettlementsEl = document.getElementById("dashPendingSettlements");
    const pendingAmountEl = document.getElementById("dashPendingAmount");
    const groupsListEl = document.getElementById("groupsList");
    const dashTimelineFeed = document.getElementById("dashTimelineFeed");

    if (totalGroupsEl) totalGroupsEl.textContent = allGroups.length;

    renderGroupsList(groupsListEl);

    if (!currentGroupId) return;

    try {
        const [overview, timelineData] = await Promise.all([
            apiRequest(`/api/groups/${currentGroupId}/analytics/overview`),
            apiRequest(`/api/groups/${currentGroupId}/analytics/timeline`)
        ]);

        if (totalSpentEl) totalSpentEl.textContent = formatMoney(overview.total_expense_paise, overview.currency);
        if (budgetRemainingEl) budgetRemainingEl.textContent = formatMoney(overview.remaining_budget_paise, overview.currency);
        if (budgetPctEl) budgetPctEl.textContent = `${overview.budget_consumed_percentage}% of target budget consumed`;
        if (pendingSettlementsEl) pendingSettlementsEl.textContent = overview.pending_settlements_paise > 0 ? "Pending" : "0";
        if (pendingAmountEl) pendingAmountEl.textContent = `${formatMoney(overview.pending_settlements_paise, overview.currency)} outstanding`;

        // Render compact recent timeline on dashboard
        if (dashTimelineFeed) {
            dashTimelineFeed.innerHTML = "";
            const items = (timelineData.timeline || []).slice(0, 5);

            if (items.length === 0) {
                dashTimelineFeed.innerHTML = '<div class="empty-state">No activities recorded yet. Upload a receipt or add an expense to start.</div>';
            } else {
                items.forEach(ev => {
                    const card = document.createElement("div");
                    card.className = "timeline-card";
                    card.innerHTML = `
                        <div class="timeline-node ${ev.color || 'purple'}"></div>
                        <div class="timeline-card-header">
                            <strong>${ev.title}</strong>
                            <span class="timeline-card-date">${formatDateTime(ev.timestamp)}</span>
                        </div>
                        <div class="timeline-card-body">${ev.description}</div>
                        ${ev.amount_paise ? `<div class="timeline-card-amount">${formatMoney(ev.amount_paise)}</div>` : ''}
                    `;
                    dashTimelineFeed.appendChild(card);
                });
            }
        }

    } catch (err) {
        console.error("Dashboard error:", err);
    }
}

function renderGroupsList(container) {
    if (!container) return;
    container.innerHTML = "";

    if (allGroups.length === 0) {
        container.innerHTML = '<div class="empty-state">No groups created yet. Create your first group above!</div>';
        return;
    }

    allGroups.forEach(grp => {
        const card = document.createElement("article");
        card.className = `group-card ${grp.id === currentGroupId ? 'active-group-card' : ''}`;
        card.style.cursor = "pointer";
        card.onclick = () => onGlobalGroupChange(grp.id);

        card.innerHTML = `
            <div class="group-card-header">
                <strong>${grp.name}</strong>
                <span class="status-pill status-suggested">${(grp.activity_type || 'general').toUpperCase()}</span>
            </div>
            <p style="font-size:11px;color:var(--muted);margin:4px 0">${grp.description || 'No description provided'}</p>
            <div class="group-card-stats" style="margin-top:8px">
                <div><span>Members:</span> <strong>${grp.member_count || 0}</strong></div>
                <div><span>Total Spend:</span> <strong>${formatMoney(grp.total_expense_paise, grp.currency)}</strong></div>
            </div>
        `;
        container.appendChild(card);
    });
}

// --------------------------------------------------
// 5. GROUP CREATION & MEMBERS
// --------------------------------------------------

async function handleCreateGroup(e) {
    e.preventDefault();
    const btn = document.getElementById("createGroupBtn");
    const msg = document.getElementById("createGroupMsg");

    const name = document.getElementById("newGroupName").value.trim();
    const activity_type = document.getElementById("newGroupActivity").value;
    const budgetRupees = document.getElementById("newGroupBudget").value;
    const start_date = document.getElementById("newGroupStart").value || null;
    const end_date = document.getElementById("newGroupEnd").value || null;
    const description = document.getElementById("newGroupDesc").value.trim();

    if (!name) return;

    btn.disabled = true;
    btn.textContent = "Creating...";

    try {
        const payload = {
            name,
            activity_type,
            budget_paise: budgetRupees ? Math.round(Number(budgetRupees) * 100) : 0,
            start_date: start_date ? new Date(start_date).toISOString() : null,
            end_date: end_date ? new Date(end_date).toISOString() : null,
            description: description || null,
            currency: "INR"
        };

        const newGrp = await apiRequest("/api/groups/", {
            method: "POST",
            body: JSON.stringify(payload)
        });

        showToast(`Group "${newGrp.name}" created successfully!`, "success");
        document.getElementById("groupCreateForm").reset();

        await loadGroups();
        currentGroupId = newGrp.id;
        document.getElementById("globalGroupSelect").value = currentGroupId;
        await onActiveGroupChanged();

    } catch (err) {
        showMessage(msg, err.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "＋ Create Group Activity";
    }
}

async function handleAddMember(e) {
    e.preventDefault();
    if (!currentGroupId) {
        showToast("Please select a group first.", "error");
        return;
    }

    const btn = document.getElementById("addMemberBtn");
    const msg = document.getElementById("addMemberMsg");

    const name = document.getElementById("newMemberName").value.trim();
    const role = document.getElementById("newMemberRole").value;
    const email = document.getElementById("newMemberEmail").value.trim() || null;
    const phone = document.getElementById("newMemberPhone").value.trim() || null;

    btn.disabled = true;
    btn.textContent = "Adding...";

    try {
        const newMember = await apiRequest(`/api/groups/${currentGroupId}/members`, {
            method: "POST",
            body: JSON.stringify({ name, role, email, phone })
        });

        showToast(`Member ${newMember.name} added!`, "success");
        document.getElementById("memberAddForm").reset();

        await loadGroupMembers();
        await loadDashboard();

    } catch (err) {
        showMessage(msg, err.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "＋ Add Member";
    }
}

// --------------------------------------------------
// 6. ACTIVITY TIMELINE
// --------------------------------------------------

let timelineEvents = [];

async function loadTimeline() {
    if (!currentGroupId) return;
    const container = document.getElementById("timelineContainer");
    if (!container) return;

    container.innerHTML = '<div class="empty-state">Loading group activity timeline...</div>';

    try {
        const data = await apiRequest(`/api/groups/${currentGroupId}/analytics/timeline`);
        timelineEvents = data.timeline || [];
        renderTimelineFiltered("all");
    } catch (err) {
        container.innerHTML = `<div class="empty-state">Failed to load timeline: ${err.message}</div>`;
    }
}

function filterTimeline(type, btn) {
    document.querySelectorAll(".timeline-filters .filter-pill").forEach(p => p.classList.remove("active"));
    if (btn) btn.classList.add("active");
    renderTimelineFiltered(type);
}

function renderTimelineFiltered(type) {
    const container = document.getElementById("timelineContainer");
    if (!container) return;

    container.innerHTML = "";
    const filtered = type === "all" ? timelineEvents : timelineEvents.filter(ev => ev.type === type);

    if (filtered.length === 0) {
        container.innerHTML = '<div class="empty-state">No events match the selected filter.</div>';
        return;
    }

    filtered.forEach(ev => {
        const card = document.createElement("div");
        card.className = "timeline-card";
        card.innerHTML = `
            <div class="timeline-node ${ev.color || 'purple'}"></div>
            <div class="timeline-card-header">
                <div>
                    <strong>${ev.title}</strong>
                    <span class="status-pill status-suggested" style="margin-left:6px">${ev.badge || ev.type}</span>
                </div>
                <span class="timeline-card-date">${formatDateTime(ev.timestamp)}</span>
            </div>
            <div class="timeline-card-body">${ev.description}</div>
            ${ev.amount_paise ? `<div class="timeline-card-amount">${formatMoney(ev.amount_paise)}</div>` : ''}
        `;
        container.appendChild(card);
    });
}

// --------------------------------------------------
// 7. EXPENSES MANAGEMENT
// --------------------------------------------------

function setSplitType(type) {
    currentSplitType = type;
    document.querySelectorAll(".split-type-toggle .radio-tab").forEach(tab => {
        const input = tab.querySelector("input");
        if (input && input.value === type) tab.classList.add("active");
        else tab.classList.remove("active");
    });
    renderParticipantsCheckboxes();
    onExpenseAmountOrSplitChange();
}

function renderParticipantsCheckboxes() {
    const container = document.getElementById("participantsList");
    if (!container) return;

    container.innerHTML = "";
    if (currentGroupMembers.length === 0) {
        container.innerHTML = '<div class="empty-state">Add group members first.</div>';
        return;
    }

    currentGroupMembers.forEach(m => {
        const row = document.createElement("div");
        row.className = "participant-item";

        const label = document.createElement("label");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.value = m.id;
        checkbox.checked = true;
        checkbox.dataset.memberId = m.id;
        checkbox.onchange = onExpenseAmountOrSplitChange;

        label.appendChild(checkbox);
        label.appendChild(document.createTextNode(m.name));

        row.appendChild(label);

        if (currentSplitType === "percentage") {
            const input = document.createElement("input");
            input.type = "number";
            input.step = "0.1";
            input.className = "participant-share-input";
            input.placeholder = "%";
            input.dataset.percentageId = m.id;
            input.oninput = onExpenseAmountOrSplitChange;
            row.appendChild(input);
        } else if (currentSplitType === "custom") {
            const input = document.createElement("input");
            input.type = "number";
            input.step = "0.01";
            input.className = "participant-share-input";
            input.placeholder = "₹";
            input.dataset.customShareId = m.id;
            input.oninput = onExpenseAmountOrSplitChange;
            row.appendChild(input);
        }

        container.appendChild(row);
    });
}

function toggleAllParticipants(check) {
    document.querySelectorAll('#participantsList input[type="checkbox"]').forEach(cb => {
        cb.checked = check;
    });
    onExpenseAmountOrSplitChange();
}

function onExpenseAmountOrSplitChange() {
    const feedback = document.getElementById("splitFeedback");
    if (!feedback) return;

    const amountVal = parseFloat(document.getElementById("expAmount").value) || 0;
    const selectedBoxes = Array.from(document.querySelectorAll('#participantsList input[type="checkbox"]:checked'));
    const selectedIds = selectedBoxes.map(cb => Number(cb.dataset.memberId));

    if (selectedIds.length === 0) {
        feedback.textContent = "Select at least one participant.";
        feedback.style.color = "#ef4444";
        return;
    }

    if (currentSplitType === "equal") {
        if (amountVal > 0) {
            const perPerson = amountVal / selectedIds.length;
            feedback.textContent = `₹${amountVal.toFixed(2)} will be divided equally: ₹${perPerson.toFixed(2)} across ${selectedIds.length} participant(s). Exact paise distributed automatically.`;
            feedback.style.color = "#10b981";
        } else {
            feedback.textContent = `Equal split across ${selectedIds.length} participant(s).`;
            feedback.style.color = "#7c8299";
        }
    } else if (currentSplitType === "percentage") {
        let totalPct = 0;
        document.querySelectorAll("[data-percentage-id]").forEach(input => {
            if (selectedIds.includes(Number(input.dataset.percentageId))) {
                totalPct += parseFloat(input.value) || 0;
            }
        });
        if (Math.abs(totalPct - 100) < 0.1) {
            feedback.textContent = `Percentages total 100%! Ready to save.`;
            feedback.style.color = "#10b981";
        } else {
            feedback.textContent = `Percentages currently sum to ${totalPct.toFixed(1)}% (needs 100%).`;
            feedback.style.color = "#ef4444";
        }
    } else if (currentSplitType === "custom") {
        let totalCustom = 0;
        document.querySelectorAll("[data-custom-share-id]").forEach(input => {
            if (selectedIds.includes(Number(input.dataset.customShareId))) {
                totalCustom += parseFloat(input.value) || 0;
            }
        });
        const diff = amountVal - totalCustom;
        if (Math.abs(diff) < 0.01) {
            feedback.textContent = `Custom shares equal total amount of ₹${amountVal.toFixed(2)}.`;
            feedback.style.color = "#10b981";
        } else {
            feedback.textContent = `Custom shares sum to ₹${totalCustom.toFixed(2)}. Difference: ₹${diff.toFixed(2)}.`;
            feedback.style.color = "#ef4444";
        }
    }
}

async function handleSaveExpense(e) {
    e.preventDefault();
    if (!currentGroupId) return;

    const btn = document.getElementById("saveExpenseBtn");
    const msg = document.getElementById("saveExpenseMsg");

    const description = document.getElementById("expDesc").value.trim();
    const amountRupees = parseFloat(document.getElementById("expAmount").value);
    const category = document.getElementById("expCategory").value;
    const paidByMemberId = Number(document.getElementById("expPayer").value);
    const merchant = document.getElementById("expMerchant").value.trim() || null;
    const evidenceId = document.getElementById("expEvidenceSelect").value || null;

    const selectedBoxes = Array.from(document.querySelectorAll('#participantsList input[type="checkbox"]:checked'));
    const participantIds = selectedBoxes.map(cb => Number(cb.dataset.memberId));

    if (!description || !amountRupees || !paidByMemberId || participantIds.length === 0) {
        showMessage(msg, "Please fill in all required fields.", "error");
        return;
    }

    const totalAmountPaise = Math.round(amountRupees * 100);
    const payload = {
        description,
        total_amount_paise: totalAmountPaise,
        paid_by_member_id: paidByMemberId,
        split_type: currentSplitType,
        participant_ids: participantIds,
        category,
        merchant,
        evidence_id: evidenceId ? Number(evidenceId) : null
    };

    if (currentSplitType === "percentage") {
        const percentages = {};
        document.querySelectorAll("[data-percentage-id]").forEach(input => {
            const mid = Number(input.dataset.percentageId);
            if (participantIds.includes(mid)) {
                percentages[mid] = parseFloat(input.value) || 0;
            }
        });
        payload.percentage_shares = percentages;
    } else if (currentSplitType === "custom") {
        const customShares = [];
        document.querySelectorAll("[data-custom-share-id]").forEach(input => {
            const mid = Number(input.dataset.customShareId);
            if (participantIds.includes(mid)) {
                customShares.push({
                    member_id: mid,
                    amount_paise: Math.round((parseFloat(input.value) || 0) * 100)
                });
            }
        });
        payload.custom_shares = customShares;
    }

    btn.disabled = true;
    btn.textContent = "Saving...";

    try {
        const createdExp = await apiRequest(`/api/groups/${currentGroupId}/expenses/`, {
            method: "POST",
            body: JSON.stringify(payload)
        });

        showToast(`Expense "${createdExp.description}" recorded!`, "success");
        document.getElementById("expenseForm").reset();
        setSplitType("equal");

        await loadExpenses();
        await loadDashboard();

    } catch (err) {
        showMessage(msg, err.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "＋ Save Expense";
    }
}

async function loadExpenses() {
    if (!currentGroupId) return;
    const container = document.getElementById("expensesHistoryList");
    const categoryFilter = document.getElementById("expenseCategoryFilter")?.value;

    if (!container) return;
    container.innerHTML = '<div class="empty-state">Loading expenses...</div>';

    try {
        let url = `/api/groups/${currentGroupId}/expenses/`;
        if (categoryFilter) url += `?category=${encodeURIComponent(categoryFilter)}`;

        currentGroupExpenses = await apiRequest(url);

        container.innerHTML = "";
        if (currentGroupExpenses.length === 0) {
            container.innerHTML = '<div class="empty-state">No expenses recorded yet. Use the form on the left to add one!</div>';
            return;
        }

        currentGroupExpenses.forEach(exp => {
            const payer = currentGroupMembers.find(m => m.id === exp.paid_by_member_id);
            const payerName = payer ? payer.name : `Member #${exp.paid_by_member_id}`;

            const card = document.createElement("article");
            card.className = "expense-item";

            card.innerHTML = `
                <div class="expense-details">
                    <div style="display:flex;align-items:center;gap:8px">
                        <strong>${exp.description}</strong>
                        <span class="status-pill status-suggested">${exp.category}</span>
                        ${exp.evidence_count > 0 ? '<span class="status-pill status-confirmed">📎 Receipt Linked</span>' : ''}
                    </div>
                    <small>Paid by ${payerName} · Split: ${exp.split_type.toUpperCase()} · ${formatDateTime(exp.created_at)}</small>
                    ${exp.merchant ? `<small style="display:block;color:var(--muted)">Merchant: ${exp.merchant}</small>` : ''}
                    <div class="expense-shares" style="margin-top:6px">
                        ${exp.shares.map(s => {
                            const sm = currentGroupMembers.find(m => m.id === s.member_id);
                            return `<span class="share-chip">${sm ? sm.name : '#' + s.member_id}: ${formatMoney(s.amount_paise)}</span>`;
                        }).join("")}
                    </div>
                </div>
                <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">
                    <div class="expense-item-amount">${formatMoney(exp.total_amount_paise)}</div>
                    <button class="text-btn danger-btn" onclick="deleteExpense(${exp.id})">Delete</button>
                </div>
            `;
            container.appendChild(card);
        });

    } catch (err) {
        container.innerHTML = `<div class="empty-state">Failed to load expenses: ${err.message}</div>`;
    }
}

async function deleteExpense(expenseId) {
    if (!confirm("Are you sure you want to delete this expense? All shares will be removed.")) return;
    try {
        await apiRequest(`/api/groups/${currentGroupId}/expenses/${expenseId}`, { method: "DELETE" });
        showToast("Expense deleted.", "success");
        await loadExpenses();
        await loadDashboard();
    } catch (err) {
        showToast("Could not delete expense: " + err.message, "error");
    }
}

// --------------------------------------------------
// 8. UPLOAD & EVIDENCE CENTRE
// --------------------------------------------------

function handleFileSelected(event) {
    setSelectedUploadFile(event.target.files[0]);
}

function handleDropzoneKeyDown(event) {
    if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        document.getElementById("evidenceFileInput").click();
    }
}

function handleFileDragOver(event) {
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
}

function handleFileDrop(event) {
    event.preventDefault();
    setSelectedUploadFile(event.dataTransfer?.files?.[0]);
}

function setSelectedUploadFile(file) {
    if (!file) return;
    selectedUploadFile = file;

    const preview = document.getElementById("uploadSelectedPreview");
    const nameEl = document.getElementById("previewFileName");
    const sizeEl = document.getElementById("previewFileSize");

    if (nameEl) nameEl.textContent = file.name;
    if (sizeEl) sizeEl.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
    if (preview) preview.classList.remove("hidden");
}

function cancelUploadSelection() {
    selectedUploadFile = null;
    const preview = document.getElementById("uploadSelectedPreview");
    if (preview) preview.classList.add("hidden");
    const input = document.getElementById("evidenceFileInput");
    if (input) input.value = "";
}

async function executeUpload() {
    if (!selectedUploadFile || !currentGroupId) return;

    const btn = document.getElementById("startUploadBtn");
    const msg = document.getElementById("uploadStatusMsg");
    const uploaderId = document.getElementById("evidenceUploader")?.value;
    const notes = document.getElementById("evidenceNotes")?.value;

    btn.disabled = true;
    btn.textContent = "Analyzing with AI...";
    showMessage(msg, "Extracting information & checking duplicates...");

    const formData = new FormData();
    formData.append("file", selectedUploadFile);
    if (uploaderId) formData.append("uploaded_by_member_id", uploaderId);
    if (notes) formData.append("notes", notes);

    try {
        const evidence = await apiRequest(`/api/groups/${currentGroupId}/evidence/upload`, {
            method: "POST",
            body: formData
        });

        showToast(`Evidence "${evidence.filename}" uploaded and analyzed!`, "success");
        cancelUploadSelection();
        await loadEvidenceList();

        // If extraction returned expense data, open the draft confirmation card!
        if (evidence.extracted_data) {
            showDraftReview(evidence);
        }

    } catch (err) {
        showMessage(msg, err.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "Upload & Analyze Evidence";
    }
}

function showDraftReview(evidence) {
    const card = document.getElementById("aiDraftReviewCard");
    if (!card) return;

    const ext = evidence.extracted_data || {};
    const dup = ext.duplicate_check;

    document.getElementById("draftEvidenceId").value = evidence.id;
    document.getElementById("draftDesc").value = ext.notes || ext.description || `${ext.category || 'Receipt'} - ${ext.merchant_name || evidence.filename}`;
    document.getElementById("draftAmount").value = ext.total_amount_rupees || ext.amount_rupees || "";

    if (ext.category) {
        const catSelect = document.getElementById("draftCategory");
        if (catSelect) catSelect.value = ext.category;
    }

    // Populate draft payer dropdown
    const payerSelect = document.getElementById("draftPayer");
    payerSelect.innerHTML = "";
    currentGroupMembers.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m.id;
        opt.textContent = m.name;
        payerSelect.appendChild(opt);
    });

    // Populate draft participants checkboxes
    const partContainer = document.getElementById("draftParticipantsList");
    partContainer.innerHTML = "";
    currentGroupMembers.forEach(m => {
        const row = document.createElement("div");
        row.className = "participant-item";
        row.innerHTML = `
            <label>
                <input type="checkbox" name="draftPart" value="${m.id}" checked>
                ${m.name}
            </label>
        `;
        partContainer.appendChild(row);
    });

    // Show duplicate alert if flagged
    const dupAlert = document.getElementById("duplicateAlertBox");
    const dupReason = document.getElementById("dupAlertReason");
    if (dup && dup.is_duplicate) {
        dupReason.textContent = dup.reason;
        dupAlert.classList.remove("hidden");
    } else {
        dupAlert.classList.add("hidden");
    }

    card.classList.remove("hidden");
    card.scrollIntoView({ behavior: "smooth" });
}

function hideDraftReview() {
    const card = document.getElementById("aiDraftReviewCard");
    if (card) card.classList.add("hidden");
}

async function handleConfirmDraft(e) {
    e.preventDefault();
    if (!currentGroupId) return;

    const evidenceId = Number(document.getElementById("draftEvidenceId").value);
    const description = document.getElementById("draftDesc").value.trim();
    const amountVal = parseFloat(document.getElementById("draftAmount").value);
    const payerId = Number(document.getElementById("draftPayer").value);
    const category = document.getElementById("draftCategory").value;

    const selectedParts = Array.from(document.querySelectorAll('input[name="draftPart"]:checked')).map(cb => Number(cb.value));

    if (!description || !amountVal || !payerId || selectedParts.length === 0) {
        showToast("Fill in all draft fields.", "error");
        return;
    }

    const payload = {
        group_id: currentGroupId,
        description,
        total_amount_paise: Math.round(amountVal * 100),
        paid_by_member_id: payerId,
        participant_ids: selectedParts,
        split_type: "equal",
        category,
        evidence_id: evidenceId
    };

    try {
        const exp = await apiRequest("/api/ai/confirm-draft", {
            method: "POST",
            body: JSON.stringify(payload)
        });

        showToast(`Draft confirmed! Saved expense "${exp.description}".`, "success");
        hideDraftReview();
        await loadEvidenceList();
        await loadExpenses();
        await loadDashboard();

    } catch (err) {
        showToast("Confirmation failed: " + err.message, "error");
    }
}

async function loadEvidenceList() {
    if (!currentGroupId) return;
    const gallery = document.getElementById("evidenceGallery");
    const expSelect = document.getElementById("expEvidenceSelect");

    if (!gallery) return;
    gallery.innerHTML = '<div class="empty-state">Loading evidence...</div>';

    try {
        const evidences = await apiRequest(`/api/groups/${currentGroupId}/evidence/`);

        gallery.innerHTML = "";
        if (expSelect) expSelect.innerHTML = '<option value="">No evidence attached</option>';

        if (evidences.length === 0) {
            gallery.innerHTML = '<div class="empty-state">No evidence uploaded yet. Drop a receipt or voice note above!</div>';
            return;
        }

        evidences.forEach(ev => {
            if (expSelect && ev.link_status !== "confirmed") {
                const opt = document.createElement("option");
                opt.value = ev.id;
                opt.textContent = `${ev.filename} (${ev.file_type.toUpperCase()})`;
                expSelect.appendChild(opt);
            }

            const ext = ev.extracted_data || {};
            const card = document.createElement("div");
            card.className = "evidence-card";

            const dupBadge = ext.duplicate_check?.is_duplicate
                ? `<span class="status-pill status-suggested" title="${ext.duplicate_check.reason}">⚠️ Duplicate Flag</span>`
                : '';

            card.innerHTML = `
                <div class="evidence-header">
                    <span class="status-pill status-${ev.link_status === 'confirmed' ? 'confirmed' : 'unmatched'}">${ev.link_status.toUpperCase()}</span>
                    <span class="file-size-badge">${ev.file_type.toUpperCase()}</span>
                </div>
                <div class="evidence-title" title="${ev.filename}">${ev.filename}</div>
                <div class="evidence-extracted">
                    ${ext.merchant_name ? `<div><strong>Merchant:</strong> ${ext.merchant_name}</div>` : ''}
                    ${ext.total_amount_rupees ? `<div><strong>Extracted:</strong> ₹${ext.total_amount_rupees}</div>` : ''}
                    ${ext.transcript ? `<div><strong>Voice Note:</strong> "${ext.transcript}"</div>` : ''}
                    ${ext.notes ? `<div><strong>Notes:</strong> ${ext.notes}</div>` : ''}
                    <div style="font-size:10px;color:var(--muted);margin-top:4px">${formatDateTime(ev.upload_time)}</div>
                </div>
                ${dupBadge}
                <div class="evidence-actions">
                    <a href="/api/groups/${currentGroupId}/evidence/${ev.id}/file" target="_blank" class="text-btn">View File ↗</a>
                    ${ev.link_status !== 'confirmed' ? `<button class="primary-button small-btn" onclick='showDraftReview(${JSON.stringify(ev)})'>Draft Expense</button>` : '<span class="status-pill status-confirmed">Linked</span>'}
                    <button class="text-btn danger-btn" onclick="deleteEvidence(${ev.id})">Delete</button>
                </div>
            `;
            gallery.appendChild(card);
        });

    } catch (err) {
        gallery.innerHTML = `<div class="empty-state">Failed to load evidence: ${err.message}</div>`;
    }
}

async function deleteEvidence(evId) {
    if (!confirm("Delete this evidence record?")) return;
    try {
        await apiRequest(`/api/groups/${currentGroupId}/evidence/${evId}`, { method: "DELETE" });
        showToast("Evidence removed.", "success");
        await loadEvidenceList();
    } catch (err) {
        showToast("Error: " + err.message, "error");
    }
}

// --------------------------------------------------
// 9. BUDGET & ANALYTICS
// --------------------------------------------------

async function loadAnalytics() {
    if (!currentGroupId) return;

    try {
        const [overview, categories, contributions, budgetStatus, forecast, recommendations] = await Promise.all([
            apiRequest(`/api/groups/${currentGroupId}/analytics/overview`),
            apiRequest(`/api/groups/${currentGroupId}/analytics/categories`),
            apiRequest(`/api/groups/${currentGroupId}/analytics/contributions`),
            apiRequest(`/api/groups/${currentGroupId}/analytics/budget`),
            apiRequest(`/api/groups/${currentGroupId}/analytics/forecast`),
            apiRequest(`/api/groups/${currentGroupId}/analytics/recommendations`)
        ]);

        // Budget banner
        const banner = document.getElementById("budgetHealthBanner");
        const heading = document.getElementById("budgetStatusHeading");
        const msg = document.getElementById("budgetStatusMsg");
        const bar = document.getElementById("budgetProgressBar");
        const consumedText = document.getElementById("budgetConsumedText");

        if (banner) {
            banner.className = `budget-alert-card ${budgetStatus.status_level || 'safe'}`;
            heading.textContent = `Budget Health: ${(budgetStatus.status_level || 'General').toUpperCase()}`;
            msg.textContent = budgetStatus.alert_message;
            const pct = Math.min(100, overview.budget_consumed_percentage || 0);
            if (bar) bar.style.width = `${pct}%`;
            if (consumedText) consumedText.textContent = `${overview.budget_consumed_percentage}%`;
        }

        // Category breakdown
        const catList = document.getElementById("categoryBreakdownList");
        if (catList) {
            catList.innerHTML = "";
            if (categories.length === 0) {
                catList.innerHTML = '<div class="empty-state">No category spending recorded yet.</div>';
            } else {
                categories.forEach(cat => {
                    const row = document.createElement("div");
                    row.className = "cat-bar-item";
                    row.innerHTML = `
                        <div class="cat-bar-header">
                            <span>${cat.category} (${cat.count})</span>
                            <span>${formatMoney(cat.amount_paise)} · ${cat.percentage}%</span>
                        </div>
                        <div class="cat-track">
                            <div class="cat-fill" style="width: ${Math.min(100, cat.percentage)}%"></div>
                        </div>
                    `;
                    catList.appendChild(row);
                });
            }
        }

        // Forecast
        const dailyBurn = document.getElementById("forecastDailyBurn");
        const estTotal = document.getElementById("forecastEstTotal");
        const explanation = document.getElementById("forecastExplanation");
        if (dailyBurn) dailyBurn.textContent = formatMoney(forecast.burn_rate_daily_paise);
        if (estTotal) estTotal.textContent = formatMoney(forecast.estimated_total_spending_paise);
        if (explanation) explanation.textContent = forecast.explanation;

        // Recommendations
        const recsList = document.getElementById("recommendationsList");
        if (recsList) {
            recsList.innerHTML = "";
            if (recommendations.length === 0) {
                recsList.innerHTML = '<div class="empty-state">No historical recommendations at this time.</div>';
            } else {
                recommendations.forEach(r => {
                    const item = document.createElement("div");
                    item.className = "rec-item";
                    item.innerHTML = `
                        <div class="rec-title">${r.title} (${r.category})</div>
                        <div style="color:var(--text);margin-bottom:2px">${r.recommendation}</div>
                        <div style="font-size:10px;color:var(--muted)">Based on: ${r.based_on}</div>
                    `;
                    recsList.appendChild(item);
                });
            }
        }

        // Contributions table
        const tbody = document.getElementById("contributionsTableBody");
        if (tbody) {
            tbody.innerHTML = "";
            if (contributions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No contribution records.</td></tr>';
            } else {
                contributions.forEach(c => {
                    const tr = document.createElement("tr");
                    const balClass = c.net_balance_paise > 0 ? "status-confirmed" : (c.net_balance_paise < 0 ? "status-suggested" : "status-unmatched");
                    const balLabel = c.net_balance_paise > 0
                        ? `+${formatMoney(c.net_balance_paise)} (receives)`
                        : (c.net_balance_paise < 0 ? `-${formatMoney(Math.abs(c.net_balance_paise))} (owes)` : "Settled");

                    tr.innerHTML = `
                        <td><strong>${c.member_name}</strong></td>
                        <td><span class="status-pill status-unmatched">${c.role.toUpperCase()}</span></td>
                        <td>${formatMoney(c.paid_paise)}</td>
                        <td>${formatMoney(c.owed_paise)}</td>
                        <td><span class="status-pill ${balClass}">${balLabel}</span></td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        }

    } catch (err) {
        console.error("Analytics error:", err);
    }
}

// --------------------------------------------------
// 10. SETTLEMENTS & SIMPLIFICATION
// --------------------------------------------------

async function loadSettlements() {
    if (!currentGroupId) return;

    const balancesContainer = document.getElementById("settlementBalancesList");
    const suggestionsContainer = document.getElementById("suggestedPaymentsList");
    const historyContainer = document.getElementById("settlementHistoryList");

    try {
        const [balData, simplified, history] = await Promise.all([
            apiRequest(`/api/groups/${currentGroupId}/settlements/balances`),
            apiRequest(`/api/groups/${currentGroupId}/settlements/simplified`),
            apiRequest(`/api/groups/${currentGroupId}/settlements/`)
        ]);

        // 1. Net Balances
        if (balancesContainer) {
            balancesContainer.innerHTML = "";
            const balances = balData.balances || [];
            if (balances.length === 0) {
                balancesContainer.innerHTML = '<div class="empty-state">No expenses to balance yet.</div>';
            } else {
                balances.forEach(b => {
                    const member = currentGroupMembers.find(m => m.id === b.member_id);
                    const name = member ? member.name : `Member #${b.member_id}`;
                    const bal = b.balance_paise;

                    const row = document.createElement("div");
                    row.className = "balance-item";
                    row.style.marginTop = "8px";

                    const badgeClass = bal > 0 ? "status-confirmed" : (bal < 0 ? "status-suggested" : "status-unmatched");
                    const label = bal > 0
                        ? `Should receive ${formatMoney(bal)}`
                        : (bal < 0 ? `Owes ${formatMoney(Math.abs(bal))}` : "All settled up");

                    row.innerHTML = `
                        <div class="balance-details">
                            <strong>${name}</strong>
                            <small>${label}</small>
                        </div>
                        <span class="status-pill ${badgeClass}">${formatMoney(Math.abs(bal))}</span>
                    `;
                    balancesContainer.appendChild(row);
                });
            }
        }

        // 2. Suggested simplified payments
        if (suggestionsContainer) {
            suggestionsContainer.innerHTML = "";
            const suggestions = simplified.settlements || [];
            if (suggestions.length === 0) {
                suggestionsContainer.innerHTML = '<div class="empty-state">🎉 Everyone is settled! Zero debt paths needed.</div>';
            } else {
                suggestions.forEach(s => {
                    const fromM = currentGroupMembers.find(m => m.id === s.from_member_id);
                    const toM = currentGroupMembers.find(m => m.id === s.to_member_id);
                    const fromName = fromM ? fromM.name : `Member #${s.from_member_id}`;
                    const toName = toM ? toM.name : `Member #${s.to_member_id}`;

                    const row = document.createElement("div");
                    row.className = "balance-item";
                    row.style.marginTop = "8px";
                    row.innerHTML = `
                        <div class="balance-details">
                            <strong>${fromName} → ${toName}</strong>
                            <small>${fromName} pays ${toName}</small>
                        </div>
                        <div style="display:flex;align-items:center;gap:8px">
                            <strong>${formatMoney(s.amount_paise)}</strong>
                            <button class="primary-button small-btn" onclick="recordSuggestedSettlement(${s.from_member_id}, ${s.to_member_id}, ${s.amount_paise})">Record Payment</button>
                        </div>
                    `;
                    suggestionsContainer.appendChild(row);
                });
            }
        }

        // 3. History
        if (historyContainer) {
            historyContainer.innerHTML = "";
            if (history.length === 0) {
                historyContainer.innerHTML = '<div class="empty-state">No settlement payments recorded yet.</div>';
            } else {
                history.forEach(st => {
                    const fromM = currentGroupMembers.find(m => m.id === st.from_member_id);
                    const toM = currentGroupMembers.find(m => m.id === st.to_member_id);
                    const fromName = fromM ? fromM.name : `Member #${st.from_member_id}`;
                    const toName = toM ? toM.name : `Member #${st.to_member_id}`;

                    const row = document.createElement("div");
                    row.className = "balance-item";
                    row.style.marginTop = "8px";

                    const isCompleted = st.status === "completed";
                    row.innerHTML = `
                        <div class="balance-details">
                            <strong>${fromName} → ${toName}</strong>
                            <small>${formatDateTime(st.created_at)} · Provider: ${st.payment_provider || 'Manual'}</small>
                        </div>
                        <div style="display:flex;align-items:center;gap:8px">
                            <strong>${formatMoney(st.amount_paise)}</strong>
                            <span class="status-pill status-${isCompleted ? 'confirmed' : 'suggested'}">${st.status.toUpperCase()}</span>
                            ${!isCompleted ? `<button class="secondary-button small-btn" onclick="completeSettlement(${st.id})">Mark Completed</button>` : ''}
                        </div>
                    `;
                    historyContainer.appendChild(row);
                });
            }
        }

    } catch (err) {
        console.error("Settlement load error:", err);
    }
}

async function recordSuggestedSettlement(fromId, toId, amountPaise) {
    if (!currentGroupId) return;
    try {
        await apiRequest(`/api/groups/${currentGroupId}/settlements/`, {
            method: "POST",
            body: JSON.stringify({
                from_member_id: fromId,
                to_member_id: toId,
                amount_paise: amountPaise,
                payment_provider: "Manual"
            })
        });
        showToast("Settlement record created!", "success");
        await loadSettlements();
        await loadDashboard();
    } catch (err) {
        showToast("Could not record settlement: " + err.message, "error");
    }
}

async function completeSettlement(settlementId) {
    if (!confirm("Confirm completion of this settlement payment?")) return;
    try {
        await apiRequest(`/api/groups/${currentGroupId}/settlements/${settlementId}/complete`, { method: "PATCH" });
        showToast("Settlement marked as completed!", "success");
        await loadSettlements();
        await loadDashboard();
    } catch (err) {
        showToast("Error: " + err.message, "error");
    }
}

// --------------------------------------------------
// 11. PAYPAL SANDBOX MODULE
// --------------------------------------------------

let pendingPayPalSettlements = [];
let activePayPalOrder = null;

async function loadPayPalModule() {
    if (!currentGroupId) return;
    const select = document.getElementById("paypalSettlementSelect");
    if (!select) return;

    try {
        const [settlements, transactions] = await Promise.all([
            apiRequest(`/api/groups/${currentGroupId}/settlements/?status=pending`),
            apiRequest(`/api/groups/${currentGroupId}/payments/transactions`)
        ]);

        pendingPayPalSettlements = settlements;
        select.innerHTML = '<option value="">Select a pending settlement</option>';

        if (settlements.length === 0) {
            select.innerHTML = '<option value="">No pending settlements in this group</option>';
        } else {
            settlements.forEach(st => {
                const fromM = currentGroupMembers.find(m => m.id === st.from_member_id);
                const toM = currentGroupMembers.find(m => m.id === st.to_member_id);
                const fromName = fromM ? fromM.name : `Member #${st.from_member_id}`;
                const toName = toM ? toM.name : `Member #${st.to_member_id}`;

                const opt = document.createElement("option");
                opt.value = st.id;
                opt.textContent = `Settlement #${st.id}: ${fromName} → ${toName} (${formatMoney(st.amount_paise)})`;
                select.appendChild(opt);
            });
        }

        renderPayPalTransactions(transactions);

    } catch (err) {
        console.error("PayPal module load error:", err);
    }
}

function onPayPalSettlementSelected(settlementId) {
    const calcBox = document.getElementById("paypalSelectedDetails");
    const inrEl = document.getElementById("paypalCalcINR");
    const usdEl = document.getElementById("paypalCalcUSD");

    const st = pendingPayPalSettlements.find(s => s.id === Number(settlementId));
    if (!st || !calcBox) {
        if (calcBox) calcBox.classList.add("hidden");
        return;
    }

    const inr = st.amount_paise / 100;
    const usd = (inr / 85.0).toFixed(2);

    inrEl.textContent = formatMoney(st.amount_paise);
    usdEl.textContent = `$${usd} USD`;
    calcBox.classList.remove("hidden");
}

async function handleInitiatePayPal(e) {
    e.preventDefault();
    if (!currentGroupId) return;

    const select = document.getElementById("paypalSettlementSelect");
    const settlementId = Number(select.value);
    const btn = document.getElementById("initiatePayPalBtn");
    const msg = document.getElementById("paypalInitiateMsg");

    if (!settlementId) {
        showMessage(msg, "Please select a pending settlement.", "error");
        return;
    }

    const st = pendingPayPalSettlements.find(s => s.id === settlementId);
    if (!st) return;

    btn.disabled = true;
    btn.textContent = "Connecting to PayPal Sandbox...";

    try {
        const order = await apiRequest(`/api/groups/${currentGroupId}/payments/orders`, {
            method: "POST",
            body: JSON.stringify({
                settlement_id: settlementId,
                amount_paise: st.amount_paise
            })
        });

        activePayPalOrder = order;
        activePayPalOrder.settlement_id = settlementId;

        const orderBox = document.getElementById("paypalActiveOrderBox");
        const orderIdEl = document.getElementById("paypalActiveOrderId");
        const approvalLink = document.getElementById("paypalApprovalLink");

        orderIdEl.textContent = order.order_id;
        approvalLink.href = order.approval_url || "#";

        orderBox.classList.remove("hidden");
        showToast("PayPal Sandbox Order Created! Complete buyer approval.", "success");

    } catch (err) {
        showMessage(msg, err.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "P Checkout with PayPal Sandbox";
    }
}

async function handleCapturePayPal() {
    if (!activePayPalOrder || !currentGroupId) return;

    const btn = document.getElementById("capturePayPalBtn");
    const msg = document.getElementById("capturePayPalMsg");

    btn.disabled = true;
    btn.textContent = "Capturing...";

    try {
        const res = await apiRequest(`/api/groups/${currentGroupId}/payments/capture`, {
            method: "POST",
            body: JSON.stringify({
                order_id: activePayPalOrder.order_id,
                settlement_id: activePayPalOrder.settlement_id
            })
        });

        if (res.success) {
            showToast("Payment captured successfully! Settlement marked completed.", "success");
            document.getElementById("paypalActiveOrderBox").classList.add("hidden");
            activePayPalOrder = null;
            await loadPayPalModule();
            await loadSettlements();
            await loadDashboard();
        } else {
            showMessage(msg, res.message, "error");
        }

    } catch (err) {
        showMessage(msg, err.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "✓ Capture Payment & Complete Settlement";
    }
}

function renderPayPalTransactions(transactions) {
    const container = document.getElementById("paypalTransactionsList");
    if (!container) return;

    container.innerHTML = "";
    if (!transactions || transactions.length === 0) {
        container.innerHTML = '<div class="empty-state">No PayPal transactions in this group yet.</div>';
        return;
    }

    transactions.forEach(tx => {
        const row = document.createElement("div");
        row.className = "balance-item";
        row.style.marginTop = "8px";

        const isCaptured = tx.status === "COMPLETED" || tx.status === "CAPTURED";
        row.innerHTML = `
            <div class="balance-details">
                <strong>Order: ${tx.order_id}</strong>
                <small>${formatDateTime(tx.created_at)} · Settlement #${tx.settlement_id}</small>
                ${tx.capture_id ? `<small style="display:block;color:var(--muted)">Capture ID: ${tx.capture_id}</small>` : ''}
            </div>
            <div style="display:flex;align-items:center;gap:8px">
                <strong>${formatMoney(tx.amount_paise)}</strong>
                <span class="status-pill status-${isCaptured ? 'confirmed' : 'suggested'}">${tx.status}</span>
            </div>
        `;
        container.appendChild(row);
    });
}

// --------------------------------------------------
// 12. AI FINANCIAL ASSISTANT (CHAT)
// --------------------------------------------------

async function sendChatMessage() {
    if (!currentGroupId) {
        showToast("Please select a group first.", "error");
        return;
    }

    const input = document.getElementById("chatInput");
    const message = input.value.trim();
    if (!message) return;

    input.value = "";
    appendChatMessage("user", message);

    const sendBtn = document.getElementById("sendChatBtn");
    sendBtn.disabled = true;

    try {
        const response = await apiRequest("/api/ai/chat", {
            method: "POST",
            body: JSON.stringify({
                group_id: currentGroupId,
                message
            })
        });

        appendChatMessage("assistant", response.reply, response.sources);

    } catch (err) {
        appendChatMessage("assistant", "Sorry, an error occurred while analyzing the database: " + err.message);
    } finally {
        sendBtn.disabled = false;
    }
}

function appendChatMessage(sender, text, sources = []) {
    const log = document.getElementById("chatMessageLog");
    if (!log) return;

    const msgEl = document.createElement("div");
    msgEl.className = `chat-message ${sender}`;

    const avatar = document.createElement("div");
    avatar.className = "chat-avatar";
    avatar.textContent = sender === "assistant" ? "✧" : "👤";

    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";

    const formattedText = text.replace(/\n/g, "<br>");
    bubble.innerHTML = `<p>${formattedText}</p>`;

    if (sources && sources.length > 0) {
        const srcTag = document.createElement("span");
        srcTag.className = "chat-source-tag";
        srcTag.textContent = `Sources: ${sources.join(", ")}`;
        bubble.appendChild(srcTag);
    }

    msgEl.appendChild(avatar);
    msgEl.appendChild(bubble);

    log.appendChild(msgEl);
    log.scrollTop = log.scrollHeight;
}

function askQuickPrompt(promptText) {
    const input = document.getElementById("chatInput");
    if (input) {
        input.value = promptText;
        sendChatMessage();
    }
}

function handleChatKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
    }
}

// --------------------------------------------------
// 13. DIAGNOSTICS & SETTINGS
// --------------------------------------------------

async function loadDiagnostics() {
    try {
        const [aiStatus, paypalConfig, health] = await Promise.all([
            apiRequest("/api/ai/status"),
            currentGroupId ? apiRequest(`/api/groups/${currentGroupId}/payments/config`) : { enabled: false },
            apiRequest("/health")
        ]);

        const geminiBadge = document.getElementById("geminiStatusBadge");
        const geminiModel = document.getElementById("geminiModelName");
        const paypalBadge = document.getElementById("paypalStatusBadge");

        if (geminiBadge) {
            if (aiStatus.gemini_configured) {
                geminiBadge.className = "status-pill status-confirmed";
                geminiBadge.textContent = "CONNECTED (Gemini API Active)";
            } else {
                geminiBadge.className = "status-pill status-suggested";
                geminiBadge.textContent = "HEURISTIC FALLBACK MODE (API Key Not Configured)";
            }
        }
        if (geminiModel) geminiModel.textContent = aiStatus.model;

        if (paypalBadge) {
            if (paypalConfig.enabled) {
                paypalBadge.className = "status-pill status-confirmed";
                paypalBadge.textContent = "CONNECTED (PayPal Sandbox Active)";
            } else {
                paypalBadge.className = "status-pill status-suggested";
                paypalBadge.textContent = "DEMO SIMULATION MODE (Configure .env for Live Sandbox)";
            }
        }

    } catch (err) {
        console.error("Diagnostics load error:", err);
    }
}

// --------------------------------------------------
// 14. BOOTSTRAP INITIALIZATION
// --------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

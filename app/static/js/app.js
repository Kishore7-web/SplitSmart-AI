/**
 * SplitSmart - The Financial Memory of a Group
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
let activeAIProposal = null;
let cachedActivities = [];

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
        customization: "Activities & Customization",
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
        else if (sectionId === "customization") loadCustomization();
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
    const archiveBtn = document.getElementById("archiveGroupBtn");

    if (!grp) {
        if (badge) badge.textContent = "No group selected";
        if (heroLabel) heroLabel.textContent = "Select a group";
        if (archiveBtn) archiveBtn.textContent = "Archive Group";
        return;
    }

    const typeStr = (grp.activity_type || "general").toUpperCase();
    const budgetStr = grp.budget_paise > 0 ? ` · Budget: ${formatMoney(grp.budget_paise, grp.currency)}` : "";
    const archivedStr = grp.is_archived ? " · [ARCHIVED]" : "";
    if (badge) badge.textContent = `${typeStr}${budgetStr}${archivedStr}`;
    if (heroLabel) heroLabel.textContent = grp.name;
    if (archiveBtn) {
        archiveBtn.textContent = grp.is_archived ? "Restore Group" : "Archive Group";
    }
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

    // Load group members, activities & core data
    await Promise.all([
        loadGroupMembers(),
        loadGroupActivities(),
        loadDashboard()
    ]);

    const activeHash = window.location.hash.replace("#", "") || "dashboard";
    if (activeHash !== "dashboard") {
        showSection(activeHash);
    }
}

async function loadGroupActivities() {
    if (!currentGroupId) return;
    try {
        cachedActivities = await apiRequest(`/api/groups/${currentGroupId}/activities`);
        updateActivityDropdowns(cachedActivities);
    } catch (err) {
        console.error("Failed to load group activities:", err);
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

        const right = document.createElement("div");
        right.innerHTML = `
            <button class="text-btn danger-btn small-btn" onclick="removeMember(${m.id}, '${m.name.replace(/'/g, "\\'")}')">Remove</button>
        `;

        item.appendChild(left);
        item.appendChild(right);
        container.appendChild(item);
    });
}

async function removeMember(memberId, name) {
    if (!confirm(`Are you sure you want to remove member "${name}" from this group?`)) return;
    try {
        await apiRequest(`/api/groups/${currentGroupId}/members/${memberId}`, { method: "DELETE" });
        showToast(`Member "${name}" removed.`, "success");
        await loadGroupMembers();
        await loadDashboard();
    } catch (err) {
        showToast("Could not remove member: " + err.message, "error");
    }
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
// 5B. GROUP MANAGEMENT & AI ARCHITECT
// --------------------------------------------------

function openEditGroupModal() {
    if (!currentGroupId) {
        showToast("Select a group first.", "error");
        return;
    }
    const grp = allGroups.find(g => g.id === currentGroupId);
    if (!grp) return;

    document.getElementById("editGroupName").value = grp.name || "";
    document.getElementById("editGroupBudget").value = grp.budget_paise > 0 ? (grp.budget_paise / 100).toFixed(0) : "";
    document.getElementById("editGroupActivity").value = grp.activity_type || "general";
    document.getElementById("editGroupDesc").value = grp.description || "";
    document.getElementById("editGroupModal").classList.remove("hidden");
}

function closeEditGroupModal() {
    document.getElementById("editGroupModal").classList.add("hidden");
}

async function handleUpdateGroup(e) {
    e.preventDefault();
    if (!currentGroupId) return;

    const name = document.getElementById("editGroupName").value.trim();
    const budgetRupees = document.getElementById("editGroupBudget").value;
    const activity_type = document.getElementById("editGroupActivity").value.trim();
    const description = document.getElementById("editGroupDesc").value.trim();

    if (!name) return;

    try {
        await apiRequest(`/api/groups/${currentGroupId}`, {
            method: "PATCH",
            body: JSON.stringify({
                name,
                budget_paise: budgetRupees ? Math.round(Number(budgetRupees) * 100) : 0,
                activity_type: activity_type || "general",
                description: description || null
            })
        });

        showToast("Group details updated successfully!", "success");
        closeEditGroupModal();
        await loadGroups();
    } catch (err) {
        showToast("Failed to update group: " + err.message, "error");
    }
}

async function handleArchiveActiveGroup() {
    if (!currentGroupId) return;
    const grp = allGroups.find(g => g.id === currentGroupId);
    if (!grp) return;

    if (grp.is_archived) {
        try {
            await apiRequest(`/api/groups/${currentGroupId}/restore`, { method: "POST" });
            showToast(`Group "${grp.name}" restored!`, "success");
            await loadGroups();
        } catch (err) {
            showToast("Failed to restore group: " + err.message, "error");
        }
    } else {
        if (!confirm(`Are you sure you want to archive group "${grp.name}"?`)) return;
        try {
            await apiRequest(`/api/groups/${currentGroupId}/archive`, { method: "POST" });
            showToast(`Group "${grp.name}" archived.`, "success");
            await loadGroups();
        } catch (err) {
            showToast("Failed to archive group: " + err.message, "error");
        }
    }
}

function openDeleteGroupModal() {
    if (!currentGroupId) {
        showToast("Select a group first.", "error");
        return;
    }
    document.getElementById("deleteGroupModal").classList.remove("hidden");
}

function closeDeleteGroupModal() {
    document.getElementById("deleteGroupModal").classList.add("hidden");
}

async function confirmDeleteGroup() {
    if (!currentGroupId) return;
    try {
        await apiRequest(`/api/groups/${currentGroupId}`, { method: "DELETE" });
        showToast("Group permanently deleted.", "success");
        closeDeleteGroupModal();
        currentGroupId = null;
        await loadGroups();
        showSection("groups");
    } catch (err) {
        showToast("Could not delete group: " + err.message, "error");
    }
}

async function handleAIProposeGroup() {
    const promptInput = document.getElementById("aiGroupPrompt");
    const prompt = promptInput ? promptInput.value.trim() : "";
    const btn = document.getElementById("aiProposeBtn");
    const msg = document.getElementById("aiGroupMsg");

    if (!prompt) {
        showToast("Please describe your group event or activity first.", "error");
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.textContent = "✨ Gemini is analyzing...";
    }
    showMessage(msg, "Gemini AI is structuring your group, activities, and budgets...", "normal");

    try {
        const res = await apiRequest("/api/ai/propose-group", {
            method: "POST",
            body: JSON.stringify({ prompt: prompt, description: prompt })
        });

        activeAIProposal = res.proposal || res;
        renderAIProposal(activeAIProposal);

        const previewCard = document.getElementById("aiProposalPreview");
        if (previewCard) {
            previewCard.classList.remove("hidden");
            previewCard.scrollIntoView({ behavior: "smooth" });
        }
        showMessage(msg, "Structure proposed! Review or refine below.", "success");
    } catch (err) {
        showMessage(msg, err.message, "error");
        showToast("AI proposal failed: " + err.message, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = "✨ Propose Group Structure";
        }
    }
}

function renderAIProposal(proposal) {
    if (!proposal) return;

    const nameInput = document.getElementById("propGroupName");
    const budgetInput = document.getElementById("propGroupBudget");
    const list = document.getElementById("propActivitiesList");

    if (nameInput) nameInput.value = proposal.group_name || "";
    const totalPaise = proposal.budget_paise || (proposal.overall_budget_rupees ? Math.round(parseFloat(proposal.overall_budget_rupees) * 100) : 0);
    if (budgetInput) budgetInput.value = totalPaise > 0 ? (totalPaise / 100).toFixed(0) : "";

    if (list) {
        list.innerHTML = "";
        const activities = proposal.activities || [];
        if (activities.length === 0) {
            list.innerHTML = '<span style="font-size:12px;color:var(--muted)">No sub-activities generated. Standard group structure.</span>';
        } else {
            activities.forEach(act => {
                const chip = document.createElement("div");
                chip.className = "activity-chip";
                const actPaise = act.budget_paise || (act.budget_rupees ? Math.round(parseFloat(act.budget_rupees) * 100) : 0);
                const bStr = actPaise > 0 ? ` · ${formatMoney(actPaise)}` : "";
                chip.innerHTML = `<strong>${act.name}</strong>${bStr}<br><span style="font-size:11px;color:var(--muted)">${act.description || ''}</span>`;
                list.appendChild(chip);
            });
        }
    }
}

async function handleAIRefineGroup() {
    const refineInput = document.getElementById("aiRefineInput");
    const refinePrompt = refineInput ? refineInput.value.trim() : "";
    if (!refinePrompt) {
        showToast("Enter refinement instructions first.", "error");
        return;
    }
    if (!activeAIProposal) {
        showToast("No active proposal to refine.", "error");
        return;
    }

    showToast("Refining structure with Gemini...", "normal");
    try {
        const res = await apiRequest("/api/ai/refine-group-proposal", {
            method: "POST",
            body: JSON.stringify({
                instruction: refinePrompt,
                prompt: refinePrompt,
                current_proposal: activeAIProposal
            })
        });

        activeAIProposal = res.proposal || res;
        renderAIProposal(activeAIProposal);
        if (refineInput) refineInput.value = "";
        showToast("Group structure refined!", "success");
    } catch (err) {
        showToast("Refinement failed: " + err.message, "error");
    }
}

async function handleAIConfirmGroup() {
    if (!activeAIProposal) return;

    const nameInput = document.getElementById("propGroupName");
    const budgetInput = document.getElementById("propGroupBudget");

    if (nameInput && nameInput.value.trim()) {
        activeAIProposal.group_name = nameInput.value.trim();
    }
    if (budgetInput && budgetInput.value) {
        activeAIProposal.budget_paise = Math.round(Number(budgetInput.value) * 100);
        activeAIProposal.overall_budget_rupees = Number(budgetInput.value).toFixed(2);
    }

    showToast("Creating group records in database...", "normal");
    try {
        const newGroup = await apiRequest("/api/ai/confirm-group-creation", {
            method: "POST",
            body: JSON.stringify({
                structure: activeAIProposal,
                proposal: activeAIProposal
            })
        });

        showToast(`Group "${newGroup.name}" created with custom activities!`, "success");
        const preview = document.getElementById("aiProposalPreview");
        if (preview) preview.classList.add("hidden");
        const promptInput = document.getElementById("aiGroupPrompt");
        if (promptInput) promptInput.value = "";

        await loadGroups();
        currentGroupId = newGroup.id;
        const select = document.getElementById("globalGroupSelect");
        if (select) select.value = currentGroupId;
        await onActiveGroupChanged();
        showSection("groups");
    } catch (err) {
        showToast("Creation failed: " + err.message, "error");
    }
}

// --------------------------------------------------
// 5C. ACTIVITIES & CUSTOMIZATION
// --------------------------------------------------

function showCustomTab(tabId, btn) {
    document.querySelectorAll(".tab-nav .tab-btn").forEach(b => b.classList.remove("active"));
    if (btn) btn.classList.add("active");
    document.querySelectorAll(".custom-tab-content").forEach(c => c.classList.add("hidden"));
    const target = document.getElementById(tabId);
    if (target) target.classList.remove("hidden");
}

async function loadCustomization() {
    if (!currentGroupId) return;

    const actContainer = document.getElementById("customActivitiesList");
    const catContainer = document.getElementById("customCategoriesList");
    const roleContainer = document.getElementById("customRolesList");

    try {
        const [acts, cats, roles] = await Promise.all([
            apiRequest(`/api/groups/${currentGroupId}/activities`),
            apiRequest(`/api/groups/${currentGroupId}/customization/categories`),
            apiRequest(`/api/groups/${currentGroupId}/customization/roles`)
        ]);

        cachedActivities = acts;

        // 1. Activities & Budgets
        if (actContainer) {
            actContainer.innerHTML = "";
            if (acts.length === 0) {
                actContainer.innerHTML = '<div class="empty-state">No custom activities yet. Click "+ Add Activity" above to create one.</div>';
            } else {
                acts.forEach(a => {
                    const item = document.createElement("div");
                    item.className = "balance-item";
                    item.style.marginTop = "8px";
                    const bStr = a.budget_paise > 0 ? formatMoney(a.budget_paise) : "No budget";
                    const spentStr = a.total_spent_paise ? ` · Spent: ${formatMoney(a.total_spent_paise)}` : "";
                    item.innerHTML = `
                        <div class="balance-details">
                            <div style="display:flex;align-items:center;gap:8px">
                                <strong>${a.name}</strong>
                                <span class="status-pill status-${a.status === 'active' ? 'confirmed' : 'suggested'}">${a.status.toUpperCase()}</span>
                            </div>
                            <small>Budget: ${bStr}${spentStr}${a.description ? ` · ${a.description}` : ''}</small>
                        </div>
                        <div style="display:flex;gap:6px">
                            <button class="secondary-button small-btn" onclick="openActivityModal(${a.id})">Edit</button>
                            <button class="text-btn danger-btn small-btn" onclick="deleteActivity(${a.id})">Delete</button>
                        </div>
                    `;
                    actContainer.appendChild(item);
                });
            }
        }

        // 2. Custom Categories
        if (catContainer) {
            catContainer.innerHTML = "";
            if (cats.length === 0) {
                catContainer.innerHTML = '<div class="empty-state">No custom categories defined. Default categories are active.</div>';
            } else {
                cats.forEach(c => {
                    const item = document.createElement("div");
                    item.className = "balance-item";
                    item.style.marginTop = "8px";
                    item.innerHTML = `
                        <div class="balance-details">
                            <strong>${c.icon ? c.icon + ' ' : ''}${c.name}</strong>
                            <small>${c.is_default ? 'System Default' : 'Custom Category'}</small>
                        </div>
                        <div>
                            ${!c.is_default ? `<button class="text-btn danger-btn small-btn" onclick="deleteCategory(${c.id})">Delete</button>` : '<span class="status-pill status-confirmed">Default</span>'}
                        </div>
                    `;
                    catContainer.appendChild(item);
                });
            }
        }

        // 3. Custom Roles
        if (roleContainer) {
            roleContainer.innerHTML = "";
            if (roles.length === 0) {
                roleContainer.innerHTML = '<div class="empty-state">No custom roles defined. Standard roles (Owner, Admin, Member, Viewer) are active.</div>';
            } else {
                roles.forEach(r => {
                    const item = document.createElement("div");
                    item.className = "balance-item";
                    item.style.marginTop = "8px";
                    const perms = (r.permissions || []).map(p => `<span class="share-chip">${p.permission_key}</span>`).join(" ");
                    item.innerHTML = `
                        <div class="balance-details">
                            <div style="display:flex;align-items:center;gap:8px">
                                <strong>${r.name}</strong>
                                <span class="status-pill status-suggested">ROLE</span>
                            </div>
                            <p style="font-size:12px;color:var(--muted);margin:4px 0">${r.description || 'No description'}</p>
                            <div style="margin-top:4px">${perms || '<span style="font-size:11px;color:var(--muted)">No special permissions</span>'}</div>
                        </div>
                        <div>
                            ${!r.is_system ? `<button class="text-btn danger-btn small-btn" onclick="deleteRole(${r.id})">Delete</button>` : '<span class="status-pill status-confirmed">System</span>'}
                        </div>
                    `;
                    roleContainer.appendChild(item);
                });
            }
        }

        updateActivityDropdowns(acts);
        updateCategoryDropdowns(cats);

    } catch (err) {
        console.error("Customization load error:", err);
    }
}

function updateActivityDropdowns(acts) {
    const expAct = document.getElementById("expActivity");
    const editExpAct = document.getElementById("editExpActivity");

    [expAct, editExpAct].forEach(sel => {
        if (!sel) return;
        const currentVal = sel.value;
        sel.innerHTML = '<option value="">No specific activity (Group Level)</option>';
        (acts || []).forEach(a => {
            const opt = document.createElement("option");
            opt.value = a.id;
            opt.textContent = `${a.name}${a.budget_paise > 0 ? ' (' + formatMoney(a.budget_paise) + ')' : ''}`;
            sel.appendChild(opt);
        });
        if (currentVal) sel.value = currentVal;
    });
}

function updateCategoryDropdowns(cats) {
    const dropdowns = ["expCategory", "editExpCategory", "draftCategory"];
    dropdowns.forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        const currentVal = sel.value;
        (cats || []).forEach(c => {
            if (!Array.from(sel.options).some(o => o.value === c.name)) {
                const opt = document.createElement("option");
                opt.value = c.name;
                opt.textContent = c.name;
                sel.appendChild(opt);
            }
        });
        if (currentVal) sel.value = currentVal;
    });
}

function openActivityModal(actId) {
    const modal = document.getElementById("activityModal");
    const title = document.getElementById("activityModalTitle");

    if (actId) {
        const act = cachedActivities.find(a => a.id === actId);
        if (act) {
            document.getElementById("actEditId").value = act.id;
            document.getElementById("actName").value = act.name;
            document.getElementById("actBudget").value = act.budget_paise > 0 ? (act.budget_paise / 100).toFixed(0) : "";
            document.getElementById("actDesc").value = act.description || "";
            title.textContent = "Edit Custom Activity";
        }
    } else {
        document.getElementById("actEditId").value = "";
        document.getElementById("actName").value = "";
        document.getElementById("actBudget").value = "";
        document.getElementById("actDesc").value = "";
        title.textContent = "Add Custom Activity";
    }

    modal.classList.remove("hidden");
}

function closeActivityModal() {
    document.getElementById("activityModal").classList.add("hidden");
}

async function handleSaveActivity(e) {
    e.preventDefault();
    if (!currentGroupId) return;

    const actId = document.getElementById("actEditId").value;
    const name = document.getElementById("actName").value.trim();
    const budgetRupees = document.getElementById("actBudget").value;
    const description = document.getElementById("actDesc").value.trim() || null;

    if (!name) return;

    const payload = {
        name,
        budget_paise: budgetRupees ? Math.round(Number(budgetRupees) * 100) : 0,
        description
    };

    try {
        if (actId) {
            await apiRequest(`/api/groups/${currentGroupId}/activities/${actId}`, {
                method: "PATCH",
                body: JSON.stringify(payload)
            });
            showToast("Activity updated!", "success");
        } else {
            await apiRequest(`/api/groups/${currentGroupId}/activities/`, {
                method: "POST",
                body: JSON.stringify(payload)
            });
            showToast("Activity created!", "success");
        }

        closeActivityModal();
        await loadCustomization();
    } catch (err) {
        showToast("Error saving activity: " + err.message, "error");
    }
}

async function deleteActivity(actId) {
    if (!confirm("Are you sure you want to delete this activity?")) return;
    try {
        await apiRequest(`/api/groups/${currentGroupId}/activities/${actId}`, { method: "DELETE" });
        showToast("Activity deleted.", "success");
        await loadCustomization();
    } catch (err) {
        showToast("Could not delete activity: " + err.message, "error");
    }
}

function openCategoryModal() {
    document.getElementById("catName").value = "";
    document.getElementById("categoryModal").classList.remove("hidden");
}

function closeCategoryModal() {
    document.getElementById("categoryModal").classList.add("hidden");
}

async function handleSaveCategory(e) {
    e.preventDefault();
    if (!currentGroupId) return;

    const name = document.getElementById("catName").value.trim();
    if (!name) return;

    try {
        await apiRequest(`/api/groups/${currentGroupId}/customization/categories`, {
            method: "POST",
            body: JSON.stringify({ name })
        });
        showToast(`Custom category "${name}" added!`, "success");
        closeCategoryModal();
        await loadCustomization();
    } catch (err) {
        showToast("Error adding category: " + err.message, "error");
    }
}

async function deleteCategory(catId) {
    if (!confirm("Delete this custom category?")) return;
    try {
        await apiRequest(`/api/groups/${currentGroupId}/customization/categories/${catId}`, { method: "DELETE" });
        showToast("Category deleted.", "success");
        await loadCustomization();
    } catch (err) {
        showToast("Error deleting category: " + err.message, "error");
    }
}

function openRoleModal() {
    document.getElementById("roleName").value = "";
    document.getElementById("roleDesc").value = "";
    document.querySelectorAll('input[name="rolePerm"]').forEach(cb => {
        cb.checked = ["create_expenses", "manage_evidence", "manage_settlements"].includes(cb.value);
    });
    document.getElementById("roleModal").classList.remove("hidden");
}

function closeRoleModal() {
    document.getElementById("roleModal").classList.add("hidden");
}

async function handleSaveRole(e) {
    e.preventDefault();
    if (!currentGroupId) return;

    const name = document.getElementById("roleName").value.trim();
    const description = document.getElementById("roleDesc").value.trim() || null;
    const permissions = Array.from(document.querySelectorAll('input[name="rolePerm"]:checked')).map(cb => ({ permission_key: cb.value }));

    if (!name) return;

    try {
        await apiRequest(`/api/groups/${currentGroupId}/customization/roles`, {
            method: "POST",
            body: JSON.stringify({ name, description, permissions })
        });
        showToast(`Custom role "${name}" created!`, "success");
        closeRoleModal();
        await loadCustomization();
    } catch (err) {
        showToast("Error creating role: " + err.message, "error");
    }
}

async function deleteRole(roleId) {
    if (!confirm("Delete this custom role?")) return;
    try {
        await apiRequest(`/api/groups/${currentGroupId}/customization/roles/${roleId}`, { method: "DELETE" });
        showToast("Role deleted.", "success");
        await loadCustomization();
    } catch (err) {
        showToast("Error deleting role: " + err.message, "error");
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
    const activityId = document.getElementById("expActivity")?.value || null;
    const notes = document.getElementById("expNotes")?.value.trim() || null;

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
        activity_id: activityId ? Number(activityId) : null,
        merchant,
        notes,
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
            const act = cachedActivities.find(a => a.id === exp.activity_id);
            const actChip = act ? `<span class="status-pill status-suggested">🏷 ${act.name}</span>` : '';

            const card = document.createElement("article");
            card.className = "expense-item";

            card.innerHTML = `
                <div class="expense-details">
                    <div style="display:flex;align-items:center;gap:8px">
                        <strong>${exp.description}</strong>
                        <span class="status-pill status-suggested">${exp.category}</span>
                        ${actChip}
                        ${exp.evidence_count > 0 ? '<span class="status-pill status-confirmed">📎 Receipt Linked</span>' : ''}
                    </div>
                    <small>Paid by ${payerName} · Split: ${exp.split_type.toUpperCase()} · ${formatDateTime(exp.created_at)}</small>
                    ${exp.merchant ? `<small style="display:block;color:var(--muted)">Merchant: ${exp.merchant}</small>` : ''}
                    ${exp.notes ? `<small style="display:block;color:var(--muted)">Notes: ${exp.notes}</small>` : ''}
                    <div class="expense-shares" style="margin-top:6px">
                        ${exp.shares.map(s => {
                            const sm = currentGroupMembers.find(m => m.id === s.member_id);
                            return `<span class="share-chip">${sm ? sm.name : '#' + s.member_id}: ${formatMoney(s.amount_paise)}</span>`;
                        }).join("")}
                    </div>
                </div>
                <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">
                    <div class="expense-item-amount">${formatMoney(exp.total_amount_paise)}</div>
                    <div style="display:flex;gap:6px">
                        <button class="text-btn small-btn" onclick="openEditExpenseModal(${exp.id})">Edit</button>
                        <button class="text-btn danger-btn small-btn" onclick="deleteExpense(${exp.id})">Delete</button>
                    </div>
                </div>
            `;
            container.appendChild(card);
        });

    } catch (err) {
        container.innerHTML = `<div class="empty-state">Failed to load expenses: ${err.message}</div>`;
    }
}

function openEditExpenseModal(expId) {
    const exp = currentGroupExpenses.find(e => e.id === expId);
    if (!exp) return;

    document.getElementById("editExpId").value = exp.id;
    document.getElementById("editExpDesc").value = exp.description;
    document.getElementById("editExpAmount").value = (exp.total_amount_paise / 100).toFixed(2);
    document.getElementById("editExpCategory").value = exp.category || "General";
    document.getElementById("editExpMerchant").value = exp.merchant || "";
    document.getElementById("editExpNotes").value = exp.notes || "";

    const payerSelect = document.getElementById("editExpPayer");
    payerSelect.innerHTML = "";
    currentGroupMembers.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m.id;
        opt.textContent = `${m.name} (${m.role})`;
        if (m.id === exp.paid_by_member_id) opt.selected = true;
        payerSelect.appendChild(opt);
    });

    const actSelect = document.getElementById("editExpActivity");
    if (actSelect) {
        actSelect.innerHTML = '<option value="">No specific activity</option>';
        cachedActivities.forEach(a => {
            const opt = document.createElement("option");
            opt.value = a.id;
            opt.textContent = a.name;
            if (a.id === exp.activity_id) opt.selected = true;
            actSelect.appendChild(opt);
        });
    }

    document.getElementById("editExpenseModal").classList.remove("hidden");
}

function closeEditExpenseModal() {
    document.getElementById("editExpenseModal").classList.add("hidden");
}

async function handleUpdateExpense(e) {
    e.preventDefault();
    if (!currentGroupId) return;

    const expId = document.getElementById("editExpId").value;
    const description = document.getElementById("editExpDesc").value.trim();
    const amountRupees = parseFloat(document.getElementById("editExpAmount").value);
    const category = document.getElementById("editExpCategory").value;
    const paidByMemberId = Number(document.getElementById("editExpPayer").value);
    const activityId = document.getElementById("editExpActivity").value;
    const merchant = document.getElementById("editExpMerchant").value.trim() || null;
    const notes = document.getElementById("editExpNotes").value.trim() || null;

    if (!description || !amountRupees || !paidByMemberId) {
        showToast("Fill in all required fields.", "error");
        return;
    }

    const payload = {
        description,
        total_amount_paise: Math.round(amountRupees * 100),
        paid_by_member_id: paidByMemberId,
        category,
        activity_id: activityId ? Number(activityId) : null,
        merchant,
        notes
    };

    try {
        await apiRequest(`/api/groups/${currentGroupId}/expenses/${expId}`, {
            method: "PATCH",
            body: JSON.stringify(payload)
        });

        showToast("Expense updated and shares recalculated!", "success");
        closeEditExpenseModal();
        await loadExpenses();
        await loadDashboard();
    } catch (err) {
        showToast("Failed to update expense: " + err.message, "error");
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
                        <div style="display:flex;align-items:center;gap:6px">
                            <strong>${formatMoney(s.amount_paise)}</strong>
                            <button class="primary-button small-btn" onclick="recordSuggestedSettlement(${s.from_member_id}, ${s.to_member_id}, ${s.amount_paise})">Record Full</button>
                            <button class="secondary-button small-btn" onclick="openPartialSettlementModal(${s.from_member_id}, ${s.to_member_id}, ${s.amount_paise}, '${fromName.replace(/'/g, "\\'")}', '${toName.replace(/'/g, "\\'")}')">Custom / Partial</button>
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
                    const isCancelled = st.status === "cancelled";
                    const badgeClass = isCompleted ? "status-confirmed" : (isCancelled ? "status-unmatched" : "status-suggested");

                    row.innerHTML = `
                        <div class="balance-details">
                            <strong>${fromName} → ${toName}</strong>
                            <small>${formatDateTime(st.created_at)} · Provider: ${st.payment_provider || 'Manual'}${st.notes ? ' · Note: ' + st.notes : ''}</small>
                        </div>
                        <div style="display:flex;align-items:center;gap:6px">
                            <strong>${formatMoney(st.amount_paise)}</strong>
                            <span class="status-pill ${badgeClass}">${st.status.toUpperCase()}</span>
                            ${!isCompleted && !isCancelled ? `
                                <button class="secondary-button small-btn" onclick="completeSettlement(${st.id})">Mark Completed</button>
                                <button class="secondary-button small-btn" onclick="selectPayPalSettlement(${st.id})">Pay via PayPal</button>
                                <button class="text-btn danger-btn small-btn" onclick="cancelSettlement(${st.id})">Cancel</button>
                            ` : ''}
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

function openPartialSettlementModal(fromId, toId, maxPaise, fromName, toName) {
    document.getElementById("settleFromId").value = fromId;
    document.getElementById("settleToId").value = toId;
    document.getElementById("settleParticipantsInfo").textContent = `${fromName} owes ${toName} (Suggested: ${formatMoney(maxPaise)})`;
    document.getElementById("settleAmount").value = (maxPaise / 100).toFixed(2);
    document.getElementById("settleNotes").value = "";
    document.getElementById("partialSettlementModal").classList.remove("hidden");
}

function closePartialSettlementModal() {
    document.getElementById("partialSettlementModal").classList.add("hidden");
}

async function handleRecordCustomSettlement(e) {
    e.preventDefault();
    if (!currentGroupId) return;

    const fromId = Number(document.getElementById("settleFromId").value);
    const toId = Number(document.getElementById("settleToId").value);
    const amountVal = parseFloat(document.getElementById("settleAmount").value);
    const provider = document.getElementById("settleProvider").value;
    const notes = document.getElementById("settleNotes").value.trim() || null;

    if (!fromId || !toId || !amountVal) {
        showToast("Please provide valid payment amount.", "error");
        return;
    }

    try {
        await apiRequest(`/api/groups/${currentGroupId}/settlements/`, {
            method: "POST",
            body: JSON.stringify({
                from_member_id: fromId,
                to_member_id: toId,
                amount_paise: Math.round(amountVal * 100),
                payment_provider: provider,
                notes
            })
        });

        showToast("Settlement payment recorded!", "success");
        closePartialSettlementModal();
        await loadSettlements();
        await loadDashboard();
    } catch (err) {
        showToast("Could not record settlement: " + err.message, "error");
    }
}

async function cancelSettlement(settlementId) {
    if (!confirm("Are you sure you want to cancel this settlement?")) return;
    try {
        await apiRequest(`/api/groups/${currentGroupId}/settlements/${settlementId}/cancel`, { method: "PATCH" });
        showToast("Settlement cancelled.", "success");
        await loadSettlements();
        await loadDashboard();
    } catch (err) {
        showToast("Error cancelling settlement: " + err.message, "error");
    }
}

function selectPayPalSettlement(settlementId) {
    showSection("paypal");
    const select = document.getElementById("paypalSettlementSelect");
    if (select) {
        select.value = settlementId;
        onPayPalSettlementSelected(settlementId);
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
                paypalBadge.textContent = "STANDBY MODE (Configure PAYPAL_CLIENT_ID in .env for Live Sandbox)";
            }
        }

    } catch (err) {
        console.error("Diagnostics load error:", err);
    }
}

// --------------------------------------------------
// 14. BOOTSTRAP INITIALIZATION & MODAL HANDLERS
// --------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
    initApp();

    // Close any active modal when clicking outside modal card
    document.querySelectorAll(".modal-overlay").forEach(overlay => {
        overlay.addEventListener("click", (e) => {
            if (e.target === overlay) {
                overlay.classList.add("hidden");
            }
        });
    });

    // Close on Escape key
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            document.querySelectorAll(".modal-overlay:not(.hidden)").forEach(m => m.classList.add("hidden"));
        }
    });
});

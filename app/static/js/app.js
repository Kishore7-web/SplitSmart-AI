
const API = "";

let groups = [];

async function apiRequest(url, options = {}) {
    const response = await fetch(API + url, {
        headers: {
            "Content-Type": "application/json"
        },
        ...options
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "Something went wrong.");
    }

    return data;
}


async function loadDashboard() {
    try {
        groups = await apiRequest("/api/groups/");

        document.getElementById("totalGroups").textContent = groups.length;

        const groupsList = document.getElementById("groupsList");
        groupsList.innerHTML = "";

        const selectors = [
            "expenseGroup",
            "aiGroup",
            "settlementGroup"
        ];

        selectors.forEach(id => {
            document.getElementById(id).innerHTML =
                '<option value="">Select a group</option>';
        });

        let totalMembers = 0;
        let totalExpenses = 0;
        let pendingSettlements = 0;

        for (const group of groups) {
            const members = await apiRequest(
                `/api/groups/${group.id}/members`
            );

            const expenses = await apiRequest(
                `/api/groups/${group.id}/expenses/`
            );

            const settlements = await apiRequest(
                `/api/groups/${group.id}/settlements/`
            );

            totalMembers += members.length;

            totalExpenses += expenses.reduce(
                (sum, expense) => sum + expense.total_amount_paise,
                0
            );

            pendingSettlements += settlements.filter(
                item => item.status === "pending"
            ).length;

            const item = document.createElement("div");
            item.className = "group-item";

            const title = document.createElement("strong");
            title.textContent = group.name;

            const description = document.createElement("small");
            description.textContent =
                group.description || "No description";

            const button = document.createElement("button");
            button.textContent = "View group";
            button.onclick = () => selectExpenseGroup(group.id);

            item.append(title, description, button);
            groupsList.appendChild(item);

            selectors.forEach(id => {
                const option = document.createElement("option");
                option.value = group.id;
                option.textContent = group.name;
                document.getElementById(id).appendChild(option);
            });
        }

        document.getElementById("totalMembers").textContent =
            totalMembers;

        document.getElementById("totalExpenses").textContent =
            formatMoney(totalExpenses);

        document.getElementById("pendingSettlements").textContent =
            pendingSettlements;

        if (groups.length === 0) {
            groupsList.innerHTML =
                '<p class="muted">No groups created yet.</p>';
        }

    } catch (error) {
        console.error(error);
        document.getElementById("groupsList").textContent =
            "Could not load groups: " + error.message;
    }
}


function formatMoney(paise) {
    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR"
    }).format(paise / 100);
}


document.getElementById("groupForm").addEventListener(
    "submit",
    async function(event) {
        event.preventDefault();

        const message = document.getElementById("groupMessage");

        try {
            await apiRequest("/api/groups/", {
                method: "POST",
                body: JSON.stringify({
                    name: document.getElementById("groupName").value,
                    description:
                        document.getElementById("groupDescription").value || null
                })
            });

            message.textContent = "Group created successfully!";
            message.style.color = "green";

            this.reset();
            await loadDashboard();

        } catch (error) {
            message.textContent = error.message;
            message.style.color = "red";
        }
    }
);


async function selectExpenseGroup(groupId) {
    document.getElementById("expenseGroup").value = groupId;
    document.getElementById("expenseGroupInfo").textContent =
        "Loading expenses...";

    try {
        const expenses = await apiRequest(
            `/api/groups/${groupId}/expenses/`
        );

        const container = document.getElementById("expenseGroupInfo");
        container.innerHTML = "";

        if (!expenses.length) {
            container.textContent = "No expenses recorded yet.";
            return;
        }

        expenses.forEach(expense => {
            const item = document.createElement("div");
            item.className = "result-item";

            const description = document.createElement("span");
            description.textContent = expense.description;

            const amount = document.createElement("strong");
            amount.textContent = formatMoney(expense.total_amount_paise);

            item.append(description, amount);
            container.appendChild(item);
        });

        document.getElementById("expenses").scrollIntoView({
            behavior: "smooth"
        });

    } catch (error) {
        document.getElementById("expenseGroupInfo").textContent =
            error.message;
    }
}


document.getElementById("expenseGroup").addEventListener(
    "change",
    function() {
        if (this.value) {
            selectExpenseGroup(Number(this.value));
        }
    }
);


async function createAIExpense() {
    const groupId = document.getElementById("aiGroup").value;
    const text = document.getElementById("aiText").value;
    const button = document.getElementById("aiButton");
    const result = document.getElementById("aiResult");

    if (!groupId || !text.trim()) {
        result.textContent = "Select a group and describe your expense.";
        result.style.color = "red";
        return;
    }

    button.disabled = true;
    button.textContent = "Processing...";
    result.textContent = "AI is analyzing your expense...";

    try {
        const expense = await apiRequest("/api/ai/create-expense", {
            method: "POST",
            body: JSON.stringify({
                group_id: Number(groupId),
                text: text
            })
        });

        result.style.color = "green";
        result.textContent =
            `Successfully created "${expense.description}" for ` +
            `${formatMoney(expense.total_amount_paise)}.`;

        document.getElementById("aiText").value = "";

        await loadDashboard();
        await selectExpenseGroup(Number(groupId));

    } catch (error) {
        result.style.color = "red";
        result.textContent = error.message;

    } finally {
        button.disabled = false;
        button.textContent = "✧ Analyze and Create Expense";
    }
}


document.getElementById("settlementGroup").addEventListener(
    "change",
    async function() {
        const groupId = this.value;
        const container = document.getElementById("balanceList");

        if (!groupId) {
            container.textContent = "Select a group to view balances.";
            return;
        }

        container.textContent = "Loading balances...";

        try {
            const result = await apiRequest(
                `/api/groups/${groupId}/settlements/balances`
            );

            const members = await apiRequest(
                `/api/groups/${groupId}/members`
            );

            container.innerHTML = "";

            result.balances.forEach(balance => {
                const member = members.find(
                    item => item.id === balance.member_id
                );

                const item = document.createElement("div");
                item.className = "result-item";

                const name = document.createElement("span");
                name.textContent = member ? member.name : "Member";

                const amount = document.createElement("strong");

                if (balance.balance_paise > 0) {
                    amount.textContent =
                        "Gets back " + formatMoney(balance.balance_paise);
                    amount.style.color = "green";
                } else if (balance.balance_paise < 0) {
                    amount.textContent =
                        "Owes " + formatMoney(-balance.balance_paise);
                    amount.style.color = "#d65b5b";
                } else {
                    amount.textContent = "Settled";
                }

                item.append(name, amount);
                container.appendChild(item);
            });

            if (!result.balances.length) {
                container.textContent = "No balances available yet.";
            }

        } catch (error) {
            container.textContent = error.message;
        }
    }
);


function showSection(sectionId) {
    document.getElementById(sectionId).scrollIntoView({
        behavior: "smooth"
    });
}


loadDashboard();

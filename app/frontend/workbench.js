"use strict";
const main = document.querySelector("main");
const views = Array.from(main.children).filter(el =>
    el.id || el.matches('a[href="#review"]'));
const menu = Array.from(document.querySelectorAll("aside nav a"));

function route() {
    const target = document.getElementById(location.hash.slice(1)) || document.getElementById("home");
    const panel = views.find(el => el.contains(target)) || document.getElementById("home");
    const inQueue = ["queue", "review", "amount-tasks"].includes(panel.id);
    for (const view of views) {
        const queuePanel = ["queue", "review", "amount-tasks"].includes(view.id);
        view.hidden = view !== panel && !(inQueue && queuePanel);
    }
    const selected = menu.find(link => link.hash === "#" + panel.id) ||
        menu.find(link => link.hash === (inQueue ? "#queue" : "#home"));
    for (const link of menu) {
        if (link === selected) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
    }
    document.getElementById("breadcrumb").textContent =
        panel.id.startsWith("matter-") ? "事项详情" : selected.lastChild.textContent;
    if (["imports", "briefs"].includes(panel.id)) {
        const details = panel.querySelector("details");
        if (details) details.open = true;
    }
    for (let node = target; node && node !== main; node = node.parentElement) {
        if (node.tagName === "DETAILS") node.open = true;
    }
    if ((panel === target && !inQueue) || !location.hash || target.id === "queue") window.scrollTo(0, 0);
    else target.scrollIntoView({block:"start"});
}

const search = document.getElementById("search");
const filters = Array.from(document.querySelectorAll(".filters button"));
let kind = "全部";
function filterItems() {
    const term = search.value.trim().toLocaleLowerCase();
    let count = 0;
    for (const item of document.querySelectorAll("#items .item")) {
        item.hidden = (kind !== "全部" && item.dataset.kind !== kind) ||
            !item.textContent.toLocaleLowerCase().includes(term);
        if (!item.hidden) count++;
    }
    document.getElementById("empty").hidden = count > 0;
}
search.addEventListener("input", filterItems);
for (const button of filters) {
    button.addEventListener("click", () => {
        kind = button.textContent;
        for (const option of filters) option.setAttribute("aria-pressed", String(option === button));
        filterItems();
    });
}
window.addEventListener("hashchange", route);
route();

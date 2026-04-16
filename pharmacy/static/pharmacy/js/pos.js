/**
 * Point of sale: cart, optional offline queue, catalog snapshot.
 */
(function () {
  const isSw = (document.documentElement.lang || "").toLowerCase().startsWith("sw");
  const dataEl = document.getElementById("medicines-data");
  const searchEl = document.getElementById("pos-search");
  const listEl = document.getElementById("medicine-list");
  const cartEl = document.getElementById("cart-lines");
  const totalEl = document.getElementById("cart-total-amount");
  const hiddenJson = document.getElementById("cart-json");
  const form = document.getElementById("pos-form");
  const offlinePanel = document.getElementById("offline-receipt-panel");
  const offlinePanelBody = document.getElementById("offline-receipt-body");

  if (!listEl || !form) return;

  let medicines = [];

  function formatMoney(n) {
    const v = Number(n);
    if (Number.isNaN(v)) return "—";
    return "TZS " + v.toLocaleString("en-TZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  /** @type {Map<number, {id:number,name:string,price:string,quantity:number,cartQty:number}>} */
  const cart = new Map();

  function renderList(filter) {
    const q = (filter || "").trim().toLowerCase();
    listEl.innerHTML = "";
    const rows = medicines.filter((m) => {
      if (!q) return true;
      return m.name.toLowerCase().includes(q);
    });

    if (!rows.length) {
      listEl.innerHTML =
        '<div class="empty-state">' +
        (isSw
          ? "Hakuna dawa zinazolingana na utafutaji wako. Ukiwa nje ya mtandao tumia katalogi ya mwisho iliyohifadhiwa."
          : "No medicines match your search. If you are offline, use the last catalog from when you were online.") +
        "</div>";
      return;
    }

    rows.forEach((m) => {
      const row = document.createElement("div");
      row.className = "medicine-item";
      const inCart = cart.get(m.id);
      const avail = m.quantity - (inCart ? inCart.cartQty : 0);
      row.innerHTML = `
        <div class="medicine-item-info">
          <strong>${escapeHtml(m.name)}</strong>
          <span class="medicine-item-meta">${formatMoney(m.price)} · ${avail} in stock</span>
        </div>
        <button type="button" class="btn btn-primary btn-sm touch-target" data-add="${m.id}" ${avail < 1 ? "disabled" : ""}>Add</button>
      `;
      listEl.appendChild(row);
    });

    listEl.querySelectorAll("[data-add]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = Number(btn.getAttribute("data-add"));
        addLine(id);
      });
    });
  }

  function addLine(id) {
    const m = medicines.find((x) => x.id === id);
    if (!m) return;
    const existing = cart.get(id);
    const currentQty = existing ? existing.cartQty : 0;
    if (currentQty >= m.quantity) return;

    if (existing) {
      existing.cartQty += 1;
    } else {
      cart.set(id, {
        id: m.id,
        name: m.name,
        price: m.price,
        quantity: m.quantity,
        cartQty: 1,
      });
    }
    sync();
  }

  function setQty(id, qty) {
    const m = medicines.find((x) => x.id === id);
    if (!m) return;
    const q = Math.max(0, Math.min(Number(qty) || 0, m.quantity));
    if (q === 0) {
      cart.delete(id);
    } else {
      const row = cart.get(id);
      if (row) row.cartQty = q;
    }
    sync();
  }

  function cartTotalValue() {
    let total = 0;
    cart.forEach((line) => {
      total += Number(line.price) * line.cartQty;
    });
    return total;
  }

  function updateHidden() {
    if (!hiddenJson) return;
    const payload = [];
    cart.forEach((line) => {
      payload.push({ id: line.id, qty: line.cartQty });
    });
    hiddenJson.value = JSON.stringify(payload);
  }

  function renderCart() {
    if (!cartEl || !totalEl) return;
    cartEl.innerHTML = "";
    let total = 0;

    cart.forEach((line) => {
      const sub = Number(line.price) * line.cartQty;
      total += sub;
      const div = document.createElement("div");
      div.className = "cart-line";
      div.innerHTML = `
        <div>
          <div><strong>${escapeHtml(line.name)}</strong></div>
          <div class="medicine-item-meta">${formatMoney(line.price)} × ${line.cartQty}</div>
        </div>
        <div class="qty-control">
          <button type="button" class="qty-btn touch-target" data-dec="${line.id}" aria-label="Decrease">−</button>
          <span>${line.cartQty}</span>
          <button type="button" class="qty-btn touch-target" data-inc="${line.id}" aria-label="Increase">+</button>
        </div>
      `;
      cartEl.appendChild(div);
    });

    cartEl.querySelectorAll("[data-dec]").forEach((b) => {
      b.addEventListener("click", () => {
        const id = Number(b.getAttribute("data-dec"));
        const row = cart.get(id);
        if (row) setQty(id, row.cartQty - 1);
      });
    });
    cartEl.querySelectorAll("[data-inc]").forEach((b) => {
      b.addEventListener("click", () => {
        const id = Number(b.getAttribute("data-inc"));
        const row = cart.get(id);
        if (row) setQty(id, row.cartQty + 1);
      });
    });

    if (!cart.size) {
      cartEl.innerHTML =
        '<div class="empty-state" style="padding:1rem">' +
        (isSw ? "Kikapu kiko tupu. Ongeza bidhaa kutoka orodha." : "Cart is empty. Add items from the list.") +
        "</div>";
    }

    totalEl.textContent = formatMoney(total);
  }

  function sync() {
    renderList(searchEl ? searchEl.value : "");
    renderCart();
    updateHidden();
  }

  function showOfflineReceipt(uuid, items, total) {
    if (!offlinePanel || !offlinePanelBody) return;
    let lines = "";
    items.forEach((row) => {
      const med = medicines.find((x) => x.id === row.id);
      const name = med ? med.name : "Item #" + row.id;
      const price = med ? med.price : "?";
      lines += `<tr><td>${escapeHtml(name)}</td><td>${row.qty}</td><td>${formatMoney(Number(price) * row.qty)}</td></tr>`;
    });
    offlinePanelBody.innerHTML = `
      <p class="card-hint">${isSw ? "Namba rejea (ihifadhi):" : "Reference ID (save for your records):"} <strong>${escapeHtml(uuid)}</strong></p>
      <p class="badge badge-expiry-notice" style="margin: 0.5rem 0;">${isSw ? "Inasubiri kusawazishwa — itatumwa mtandao ukirudi" : "Pending sync — will upload when you are back online"}</p>
      <table class="data-table" style="margin-top:0.75rem;font-size:0.85rem;"><thead><tr><th>${isSw ? "Bidhaa" : "Item"}</th><th>${isSw ? "Kiasi" : "Qty"}</th><th>${isSw ? "Jumla ndogo" : "Subtotal"}</th></tr></thead><tbody>${lines}</tbody></table>
      <p style="text-align:right;font-weight:700;margin-top:0.75rem;">${isSw ? "Jumla" : "Total"}: ${formatMoney(total)}</p>
    `;
    offlinePanel.hidden = false;
    offlinePanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function snapshotCatalogIfOnline() {
    if (medicines.length && window.AfyaOffline && navigator.onLine) {
      window.AfyaOffline.saveCatalogSnapshot(medicines).catch(() => {});
    }
  }

  (async function init() {
    if (dataEl) {
      try {
        medicines = JSON.parse(dataEl.textContent);
      } catch (e) {
        medicines = [];
      }
    }
    if (!medicines.length && window.AfyaOffline) {
      const snap = await window.AfyaOffline.loadCatalogSnapshot();
      if (snap && snap.length) medicines = snap;
    }

    snapshotCatalogIfOnline();

    if (searchEl) {
      searchEl.addEventListener("input", () => renderList(searchEl.value));
    }

    form.addEventListener("submit", (e) => {
      updateHidden();
      if (!hiddenJson.value || hiddenJson.value === "[]") {
        e.preventDefault();
        alert(isSw ? "Ongeza angalau bidhaa moja kwenye kikapu kabla ya kukamilisha." : "Add at least one item to the cart before checkout.");
        return;
      }

      if (!navigator.onLine) {
        e.preventDefault();
        const items = JSON.parse(hiddenJson.value);
        const total = cartTotalValue();
        const uuid = crypto.randomUUID();
        const recordedAt = new Date().toISOString();
        (async () => {
          try {
            await window.AfyaOffline.savePending({
              offlineUuid: uuid,
              items,
              recordedAt,
            });
            await window.AfyaOffline.saveCatalogSnapshot(medicines);
            window.dispatchEvent(new Event("afya-offline-queue-changed"));
            showOfflineReceipt(uuid, items, total);
            cart.clear();
            if (offlinePanel) offlinePanel.hidden = false;
            sync();
            if (window.AfyaSync) {
              window.AfyaSync.updateBannerState();
              window.AfyaSync.refreshPendingUi();
            }
          } catch (err) {
            alert(isSw ? "Imeshindikana kuhifadhi mauzo nje ya mtandao. Kagua ruhusa za uhifadhi." : "Could not save sale offline. Check storage permissions.");
          }
        })();
        return;
      }
    });

    renderList("");
    renderCart();
    updateHidden();
  })();
})();

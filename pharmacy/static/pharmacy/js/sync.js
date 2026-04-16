/**
 * Push queued offline sales to the server when online.
 */
(function () {
  const isSw = (document.documentElement.lang || "").toLowerCase().startsWith("sw");
  function getCookie(name) {
    const v = document.cookie.match("(^|;)\\s*" + name + "\\s*=\\s*([^;]+)");
    return v ? decodeURIComponent(v.pop()) : "";
  }

  function syncUrl() {
    return document.body ? document.body.getAttribute("data-sync-url") || "" : "";
  }

  function updateBannerState() {
    const banner = document.getElementById("offline-banner");
    if (!banner || !window.AfyaOffline) return;

    const offline = !navigator.onLine;
    window.AfyaOffline.pendingCount().then((n) => {
      if (offline) {
        banner.classList.remove("is-hidden", "is-queued");
        banner.classList.add("is-offline");
        banner.innerHTML =
          isSw
            ? "<strong>Nje ya mtandao</strong> — mauzo yanahifadhiwa kwenye kifaa hiki na yatasawazishwa mtandao ukirudi."
            : "<strong>Offline</strong> — sales are stored on this device and will sync when you reconnect.";
      } else if (n > 0) {
        banner.classList.remove("is-hidden", "is-offline");
        banner.classList.add("is-queued");
        banner.innerHTML = isSw
          ? `<strong>Mauzo ${n} yanasubiri</strong> — yatatumwa seva ikiwa tayari.`
          : `<strong>${n} sale(s) queued</strong> — uploading to the server when ready.`;
      } else {
        banner.classList.add("is-hidden");
        banner.classList.remove("is-offline", "is-queued");
      }
    });
  }

  async function flushQueue() {
    const url = syncUrl();
    if (!url || !window.AfyaOffline) return { synced: 0, errors: [] };

    const pending = await window.AfyaOffline.listPending();
    if (!pending.length) return { synced: 0, errors: [] };

    const token = getCookie("csrftoken");
    let synced = 0;
    const errors = [];

    for (const row of pending) {
      try {
        const res = await fetch(url, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": token,
          },
          body: JSON.stringify({
            offline_uuid: row.offlineUuid,
            items: row.items,
            recorded_at: row.recordedAt,
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok && data.ok) {
          await window.AfyaOffline.removePending(row.offlineUuid);
          synced += 1;
          window.dispatchEvent(
            new CustomEvent("afya-sync-sale", { detail: { saleId: data.sale_id } })
          );
        } else {
          errors.push(data.error || res.statusText || "Sync failed");
          break;
        }
      } catch (e) {
        errors.push(String(e.message || e));
        break;
      }
    }

    return { synced, errors };
  }

  async function refreshPendingUi() {
    const el = document.getElementById("pending-sync-badge");
    if (!el || !window.AfyaOffline) return;
    const n = await window.AfyaOffline.pendingCount();
    el.textContent = n ? String(n) : "";
    el.classList.toggle("is-visible", n > 0);
    el.setAttribute("aria-label", n ? n + " sales waiting to sync" : "No pending sales");
    updateBannerState();
  }

  window.AfyaSync = {
    flushQueue,
    refreshPendingUi,
    updateBannerState,
  };

  document.addEventListener("DOMContentLoaded", () => {
    updateBannerState();
    refreshPendingUi();
    if (navigator.onLine) {
      flushQueue().then((r) => {
        if (r.synced) refreshPendingUi();
        const toast = document.getElementById("sync-toast");
        if (toast && r.errors.length) {
          toast.hidden = false;
          toast.textContent = r.errors[0];
        }
      });
    }
  });

  window.addEventListener("online", () => {
    updateBannerState();
    flushQueue().then(() => refreshPendingUi());
  });

  window.addEventListener("offline", () => updateBannerState());

  window.addEventListener("afya-offline-queue-changed", () => refreshPendingUi());
})();

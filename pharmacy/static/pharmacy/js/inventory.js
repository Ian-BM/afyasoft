(function () {
  const isSw = (document.documentElement.lang || "").toLowerCase().startsWith("sw");
  const dialog = document.getElementById("delete-dialog");
  const form = document.getElementById("delete-dialog-form");
  const msg = document.getElementById("delete-dialog-message");
  const cancel = document.getElementById("delete-dialog-cancel");
  if (!dialog || !form || !msg) return;

  function openDialog(el) {
    if (!el) return;
    if (typeof el.showModal === "function") el.showModal();
    else el.setAttribute("open", "open");
  }

  function closeDialog(el) {
    if (!el) return;
    if (typeof el.close === "function") el.close();
    else el.removeAttribute("open");
  }

  document.querySelectorAll(".js-open-delete").forEach((btn) => {
    btn.addEventListener("click", () => {
      const url = btn.getAttribute("data-url");
      const name = btn.getAttribute("data-medicine-name") || "this item";
      form.setAttribute("action", url);
      msg.textContent =
        (isSw
          ? "Ondoa "
          : "Remove ") +
        name +
        (isSw
          ? " kutoka stoo? Hili haliwezi kurejeshwa kama dawa imeunganishwa na mauzo ya zamani."
          : " from inventory? This cannot be undone if the item is not linked to past sales.");
      openDialog(dialog);
    });
  });

  if (cancel) {
    cancel.addEventListener("click", () => closeDialog(dialog));
  }
})();

/* Dashboard: search + category filter */
(() => {
  const search   = document.getElementById("tool-search");
  const chips    = document.querySelectorAll(".filter-chip");
  const cards    = document.querySelectorAll(".tool-card");
  const emptyMsg = document.getElementById("empty-msg");

  let activeCat = "All";
  let query = "";

  function apply() {
    let visible = 0;
    cards.forEach((c) => {
      const cat = c.dataset.category || "";
      const name = (c.dataset.name || "").toLowerCase();

      const catOk = activeCat === "All" || cat === activeCat;
      const queryOk = !query || name.includes(query);

      if (catOk && queryOk) {
        c.style.display = "";
        visible++;
      } else {
        c.style.display = "none";
      }
    });
    emptyMsg.hidden = visible > 0;
  }

  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      chips.forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      activeCat = chip.dataset.cat;
      apply();
    });
  });

  search?.addEventListener("input", () => {
    query = search.value.trim().toLowerCase();
    apply();
  });
})();

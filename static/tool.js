/* Individual tool page logic — v5.4
   Sign PDF now uses a clickable arrow pad instead of numeric X/Y fields.
*/
(() => {
  const body = document.body;
  const toolId = body.dataset.toolId;
  const isMultiple = body.dataset.multiple === "true";
  const urlOnly = body.dataset.urlOnly === "true";
  const previewMode = body.dataset.preview || "";

  const $ = (id) => document.getElementById(id);

  const dropzone = $("dropzone");
  const fileInput = $("file-input");
  const browseBtn = $("browse-btn");
  const nextBtn = $("next-btn");
  const urlInput = $("url-input");
  const backBtn = $("back-btn");
  const runBtn = $("run-btn");
  const tryBtn = $("try-btn");
  const againBtn = $("again-btn");
  const download = $("download-link");
  const resultText = $("result-text");
  const errorText = $("error-text");
  const progressFill = $("progress-fill");
  const statusText = $("status-text");

  const stageUpload = $("stage-upload");
  const stageOptions = $("stage-options");
  const stagePreview = $("stage-preview");
  const stageProgress = $("stage-progress");
  const stageResult = $("stage-result");
  const stageError = $("stage-error");

  let selectedFiles = [];
  let previewState = null;

  // ----------------------------------------------------------
  // Stage helpers
  // ----------------------------------------------------------
  function show(el) {
    [stageUpload, stageOptions, stagePreview, stageProgress, stageResult, stageError]
      .forEach((s) => s && (s.hidden = true));
    if (el) el.hidden = false;
  }

  function updateNextState() {
    if (!nextBtn) return;
    if (urlOnly) {
      nextBtn.disabled = !urlInput || !urlInput.value.trim();
    } else {
      nextBtn.disabled = selectedFiles.length === 0 && (!urlInput || !urlInput.value.trim());
    }
  }

  function reset() {
    selectedFiles = [];
    if (fileInput) fileInput.value = "";
    if (urlInput) urlInput.value = "";
    previewState = null;
    updateNextState();
    show(stageUpload);
  }

  // ----------------------------------------------------------
  // File selection
  // ----------------------------------------------------------
  function setFiles(list) {
    const arr = Array.from(list || []);
    if (!arr.length) return;
    selectedFiles = isMultiple ? arr : [arr[0]];
    updateNextState();
  }

  if (dropzone) {
    ["dragenter", "dragover"].forEach((e) =>
      dropzone.addEventListener(e, (ev) => {
        ev.preventDefault(); ev.stopPropagation();
        dropzone.classList.add("dragging");
      })
    );
    ["dragleave", "drop"].forEach((e) =>
      dropzone.addEventListener(e, (ev) => {
        ev.preventDefault(); ev.stopPropagation();
        dropzone.classList.remove("dragging");
      })
    );
    dropzone.addEventListener("drop", (e) => {
      const f = e.dataTransfer?.files;
      if (f && f.length) setFiles(f);
    });
    dropzone.addEventListener("click", (e) => {
      if (e.target === browseBtn) return;
      fileInput.click();
    });
    dropzone.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
    });
    browseBtn?.addEventListener("click", (e) => { e.stopPropagation(); fileInput.click(); });
    fileInput.addEventListener("change", (e) => setFiles(e.target.files));
  }

  urlInput?.addEventListener("input", updateNextState);

  // ----------------------------------------------------------
  // Next
  // ----------------------------------------------------------
  nextBtn?.addEventListener("click", () => {
    if (previewMode && selectedFiles.length) return startPreview();

    const summary = $("file-summary");
    if (summary) {
      if (selectedFiles.length) {
        const names = selectedFiles.map((f) => escapeHtml(f.name)).join("<br>");
        const totalSize = selectedFiles.reduce((a, f) => a + f.size, 0);
        summary.innerHTML =
          `<span class="fs-name">${selectedFiles.length} file(s) selected</span>` +
          `<span class="fs-meta">${humanSize(totalSize)}</span><br><br>${names}`;
      } else if (urlInput?.value) {
        summary.innerHTML = `<span class="fs-name">URL</span>${escapeHtml(urlInput.value)}`;
      }
    }

    const hasRealOptions = stageOptions &&
      stageOptions.querySelectorAll("input, select, textarea").length > 0;

    if (hasRealOptions && !urlOnly) show(stageOptions);
    else runConversion();
  });

  backBtn?.addEventListener("click", () => show(stageUpload));
  tryBtn?.addEventListener("click", reset);
  againBtn?.addEventListener("click", reset);

  // ============================================================
  // PREVIEW
  // ============================================================
  async function startPreview() {
    show(stagePreview);
    $("preview-loading").hidden = false;
    $("preview-strip").innerHTML = "";
    $("preview-controls").hidden = true;
    $("preview-controls").innerHTML = "";
    $("preview-filename").textContent = selectedFiles[0]?.name || "—";
    $("preview-pagecount").textContent = "Loading…";

    const fd = new FormData();
    selectedFiles.forEach((f) => fd.append("files", f, f.name));

    try {
      const res = await fetch(`/api/preview/start/${toolId}`, { method: "POST", body: fd });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || `Server error (${res.status})`);

      previewState = {
        sessionId: data.session_id,
        pageCount: data.page_count,
        filename: data.filename,
        secondaryUrl: data.secondary_url,
        secondaryName: data.secondary_filename,

        // split / rotate / reorder / toggle
        splitPoints: new Set(),
        order: Array.from({ length: data.page_count }, (_, i) => i + 1),
        selected: new Set(),
        rotations: {},
        swapFirst: null,

        // sign
        sigX: 0.60,
        sigY: 0.75,
        sigW: 0.22,
        sigPages: "last",
        sigSelected: new Set(),

        // watermarks
        wmRotation: 45,
        wmOpacity: 0.15,
      };

      $("hidden-preview_session").value = data.session_id;
      $("preview-pagecount").textContent = `${data.page_count} page(s)`;
      $("preview-loading").hidden = true;

      buildPreviewControls();
      renderPreviewStrip();
      updatePreviewHint();
      updateHiddenFields();
    } catch (err) {
      $("preview-loading").hidden = true;
      errorText.textContent = err.message || "Preview failed.";
      show(stageError);
    }
  }

  // ----------------------------------------------------------
  // Preview control panel per mode
  // ----------------------------------------------------------
  function buildPreviewControls() {
    const box = $("preview-controls");
    box.innerHTML = "";
    box.hidden = true;

    // ---------- SIGN PDF ----------
    if (previewMode === "sign") {
      box.hidden = false;
      box.innerHTML = `
        <div class="ctrl-row">
          <label class="ctrl-label">Apply signature to:</label>
          <div class="ctrl-radios">
            <label><input type="radio" name="sigpage" value="last" checked> Last page</label>
            <label><input type="radio" name="sigpage" value="all"> All pages</label>
            <label><input type="radio" name="sigpage" value="selected"> Selected pages</label>
          </div>
        </div>

        <div class="ctrl-row" id="sig-pages-row" hidden>
          <label class="ctrl-label">Select pages:</label>
          <div id="sig-pages-chips" class="chip-row"></div>
        </div>

        <div class="ctrl-row">
          <label class="ctrl-label">Move signature:</label>
          <div class="arrow-pad">
            <button type="button" class="arrow-btn arrow-up"     data-dir="up"     title="Move up">▲</button>
            <button type="button" class="arrow-btn arrow-left"   data-dir="left"   title="Move left">◀</button>
            <button type="button" class="arrow-btn arrow-center" data-dir="center" title="Reset to default position">●</button>
            <button type="button" class="arrow-btn arrow-right"  data-dir="right"  title="Move right">▶</button>
            <button type="button" class="arrow-btn arrow-down"   data-dir="down"   title="Move down">▼</button>
          </div>
          <span class="ctrl-val" id="sig-pos-val">—</span>
        </div>

        <div class="ctrl-row">
          <label class="ctrl-label">Signature size:</label>
          <input type="range" id="sig-width-range" min="0.05" max="0.6" step="0.01" value="0.22">
          <span class="ctrl-val" id="sig-width-val">22%</span>
        </div>
      `;

      // Page-selection radios
      box.querySelectorAll('input[name="sigpage"]').forEach((r) => {
        r.addEventListener("change", () => {
          previewState.sigPages = r.value;
          const row = $("sig-pages-row");
          if (row) row.hidden = r.value !== "selected";
          if (r.value === "selected") renderSigPageChips();
          renderPreviewStrip();
          updateHiddenFields();
          updatePreviewHint();
        });
      });

      // Arrow pad
      const pad = box.querySelector(".arrow-pad");
      if (pad) {
        const STEP = 0.03;
        pad.querySelectorAll(".arrow-btn").forEach((btn) => {
          btn.addEventListener("click", () => {
            const dir = btn.dataset.dir;
            if (dir === "up")     previewState.sigY = Math.max(0,    previewState.sigY - STEP);
            if (dir === "down")   previewState.sigY = Math.min(1,    previewState.sigY + STEP);
            if (dir === "left")   previewState.sigX = Math.max(0,    previewState.sigX - STEP);
            if (dir === "right")  previewState.sigX = Math.min(1,    previewState.sigX + STEP);
            if (dir === "center") { previewState.sigX = 0.60; previewState.sigY = 0.75; }
            updateSigPosLabel();
            renderPreviewStrip();
            updateHiddenFields();
            updatePreviewHint();
          });
        });
      }

      // Size slider
      const wRange = box.querySelector("#sig-width-range");
      wRange?.addEventListener("input", () => {
        previewState.sigW = parseFloat(wRange.value);
        const el = $("sig-width-val");
        if (el) el.textContent = Math.round(previewState.sigW * 100) + "%";
        renderPreviewStrip();
        updateHiddenFields();
      });

      updateSigPosLabel();
    }

    // ---------- WATERMARK (TEXT / IMAGE) ----------
    if (previewMode === "watermark-text" || previewMode === "watermark-image") {
      box.hidden = false;
      box.innerHTML = `
        <div class="ctrl-row">
          <label class="ctrl-label">Rotation:</label>
          <input type="range" id="wm-rotation" min="0" max="360" step="1" value="45">
          <span class="ctrl-val" id="wm-rotation-val">45°</span>
        </div>
        <div class="ctrl-row">
          <label class="ctrl-label">Opacity:</label>
          <input type="range" id="wm-opacity" min="0.02" max="0.5" step="0.01" value="0.15">
          <span class="ctrl-val" id="wm-opacity-val">15%</span>
        </div>
      `;
      const rRange = box.querySelector("#wm-rotation");
      const oRange = box.querySelector("#wm-opacity");
      rRange?.addEventListener("input", () => {
        previewState.wmRotation = parseFloat(rRange.value);
        const el = $("wm-rotation-val");
        if (el) el.textContent = Math.round(previewState.wmRotation) + "°";
        renderPreviewStrip();
        updateHiddenFields();
      });
      oRange?.addEventListener("input", () => {
        previewState.wmOpacity = parseFloat(oRange.value);
        const el = $("wm-opacity-val");
        if (el) el.textContent = Math.round(previewState.wmOpacity * 100) + "%";
        renderPreviewStrip();
        updateHiddenFields();
      });
    }
  }

  function updateSigPosLabel() {
    const el = $("sig-pos-val");
    if (!el || !previewState) return;
    const x = Math.round(previewState.sigX * 100);
    const y = Math.round(previewState.sigY * 100);
    el.textContent = `${x}% ↔  ${y}% ↕`;
  }

  function renderSigPageChips() {
    const chips = $("sig-pages-chips");
    if (!chips || !previewState) return;
    chips.innerHTML = "";
    for (let i = 1; i <= previewState.pageCount; i++) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "page-chip" + (previewState.sigSelected.has(i) ? " active" : "");
      chip.textContent = i;
      chip.addEventListener("click", () => {
        if (previewState.sigSelected.has(i)) previewState.sigSelected.delete(i);
        else previewState.sigSelected.add(i);
        renderSigPageChips();
        renderPreviewStrip();
        updateHiddenFields();
        updatePreviewHint();
      });
      chips.appendChild(chip);
    }
  }

  // ----------------------------------------------------------
  // Render strip
  // ----------------------------------------------------------
  function renderPreviewStrip() {
    const strip = $("preview-strip");
    strip.innerHTML = "";
    const ps = previewState;
    if (!ps) return;

    if (previewMode === "scissors") {
      ps.order.forEach((pageNum, i) => {
        strip.appendChild(makePageCard(pageNum, i + 1));
        if (i < ps.order.length - 1) strip.appendChild(makeScissors(ps.order[i]));
      });
    } else {
      ps.order.forEach((pageNum) => strip.appendChild(makePageCard(pageNum, pageNum)));
    }
  }

  function shouldShowMarker(pageNum) {
    if (!previewState) return false;
    const ps = previewState;
    if (previewMode !== "sign") return false;
    if (ps.sigPages === "last") return pageNum === ps.pageCount;
    if (ps.sigPages === "all") return true;
    if (ps.sigPages === "selected") return ps.sigSelected.has(pageNum);
    return false;
  }

  function makePageCard(pageNum, displayIndex) {
    const ps = previewState;
    const card = document.createElement("div");
    card.className = "preview-card";
    card.dataset.page = pageNum;

    const thumbWrap = document.createElement("div");
    thumbWrap.className = "preview-thumb-wrap";

    const thumb = document.createElement("img");
    thumb.className = "preview-thumb";
    thumb.src = `/api/preview/thumb/${ps.sessionId}/${pageNum}`;
    thumb.alt = `Page ${pageNum}`;
    thumb.draggable = false;
    thumbWrap.appendChild(thumb);

    if (previewMode === "toggle-remove" && ps.selected.has(pageNum)) card.classList.add("marked-remove");
    if (previewMode === "toggle-extract" && ps.selected.has(pageNum)) card.classList.add("marked-extract");
    if (previewMode === "reorder" && ps.swapFirst === pageNum) card.classList.add("swap-active");

    if (ps.rotations[pageNum]) {
      thumb.style.transform = `rotate(${ps.rotations[pageNum]}deg)`;
    }

    // Signature overlay
    if (previewMode === "sign" && ps.secondaryUrl && shouldShowMarker(pageNum)) {
      const sig = document.createElement("img");
      sig.className = "signature-marker";
      sig.src = ps.secondaryUrl;
      sig.alt = "signature";
      sig.style.left = (ps.sigX * 100) + "%";
      sig.style.top  = (ps.sigY * 100) + "%";
      sig.style.width = (ps.sigW * 100) + "%";
      thumbWrap.appendChild(sig);
    }

    // Watermark overlays
    if (previewMode === "watermark-text") {
      const wm = document.createElement("div");
      wm.className = "wm-overlay wm-text";
      const textInput = document.querySelector('input[name="text"]');
      const text = (textInput?.value || "CONFIDENTIAL").trim() || "CONFIDENTIAL";
      wm.textContent = text;
      wm.style.transform = `translate(-50%, -50%) rotate(${-ps.wmRotation}deg)`;
      wm.style.opacity = ps.wmOpacity;
      thumbWrap.appendChild(wm);
    }

    if (previewMode === "watermark-image" && ps.secondaryUrl) {
      const wm = document.createElement("img");
      wm.className = "wm-overlay wm-image";
      wm.src = ps.secondaryUrl;
      wm.style.transform = `translate(-50%, -50%) rotate(${-ps.wmRotation}deg)`;
      wm.style.opacity = ps.wmOpacity;
      thumbWrap.appendChild(wm);
    }

    const num = document.createElement("span");
    num.className = "preview-page-num";
    num.textContent = pageNum;

    const zoom = document.createElement("button");
    zoom.type = "button";
    zoom.className = "preview-zoom";
    zoom.title = "Zoom";
    zoom.innerHTML = "🔍";
    zoom.addEventListener("click", (e) => { e.stopPropagation(); openLightbox(pageNum); });

    card.appendChild(thumbWrap);
    card.appendChild(num);
    card.appendChild(zoom);

    card.addEventListener("click", (e) => {
      if (previewMode === "sign") handleSignClick(e, pageNum, thumbWrap);
      else handleCardClick(pageNum);
    });

    return card;
  }

  function makeScissors(afterPage) {
    const wrap = document.createElement("div");
    wrap.className = "preview-scissors";
    wrap.dataset.after = afterPage;
    if (previewState.splitPoints.has(afterPage)) wrap.classList.add("active");

    const line = document.createElement("div");
    line.className = "preview-scissors-line";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "preview-scissors-btn";
    btn.title = `Split after page ${afterPage}`;
    btn.innerHTML = "✂";
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const s = previewState.splitPoints;
      if (s.has(afterPage)) s.delete(afterPage); else s.add(afterPage);
      wrap.classList.toggle("active");
      updateHiddenFields();
      updatePreviewHint();
    });

    wrap.appendChild(line);
    wrap.appendChild(btn);
    wrap.appendChild(line.cloneNode());
    return wrap;
  }

  function handleCardClick(pageNum) {
    if (!previewState) return;
    const ps = previewState;

    if (previewMode === "toggle-remove" || previewMode === "toggle-extract") {
      if (ps.selected.has(pageNum)) ps.selected.delete(pageNum);
      else ps.selected.add(pageNum);
      renderPreviewStrip();
      updateHiddenFields();
      updatePreviewHint();
    } else if (previewMode === "rotate") {
      const cur = ps.rotations[pageNum] || 0;
      ps.rotations[pageNum] = (cur + 90) % 360;
      renderPreviewStrip();
      updateHiddenFields();
    } else if (previewMode === "reorder") {
      if (ps.swapFirst === null) ps.swapFirst = pageNum;
      else if (ps.swapFirst === pageNum) ps.swapFirst = null;
      else {
        const a = ps.order.indexOf(ps.swapFirst);
        const b = ps.order.indexOf(pageNum);
        [ps.order[a], ps.order[b]] = [ps.order[b], ps.order[a]];
        ps.swapFirst = null;
      }
      renderPreviewStrip();
      updateHiddenFields();
    }
  }

  function handleSignClick(e, pageNum, thumbWrap) {
    const ps = previewState;
    if (!ps) return;
    const rect = thumbWrap.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top)  / rect.height;
    ps.sigX = Math.max(0, Math.min(1, x));
    ps.sigY = Math.max(0, Math.min(1, y));
    updateSigPosLabel();
    renderPreviewStrip();
    updateHiddenFields();
    updatePreviewHint();
  }

  // ----------------------------------------------------------
  // Hidden fields / hint
  // ----------------------------------------------------------
  function updateHiddenFields() {
    if (!previewState) return;
    const ps = previewState;

    $("hidden-split_points").value =
      Array.from(ps.splitPoints).sort((a, b) => a - b).join(",");

    $("hidden-order").value = ps.order.join(",");

    if (previewMode === "toggle-remove" || previewMode === "toggle-extract") {
      $("hidden-pages").value =
        Array.from(ps.selected).sort((a, b) => a - b).join(",");
    }

    const rot = Object.entries(ps.rotations)
      .filter(([, d]) => d !== 0)
      .map(([p, d]) => `${p}:${d}`).join(",");
    $("hidden-rotations").value = rot;

    if (previewMode === "sign") {
      $("hidden-signature_x").value = ps.sigX.toFixed(4);
      $("hidden-signature_y").value = ps.sigY.toFixed(4);
      $("hidden-signature_w").value = ps.sigW.toFixed(4);
      if (ps.sigPages === "selected") {
        $("hidden-signature_pages").value =
          Array.from(ps.sigSelected).sort((a, b) => a - b).join(",") || "last";
      } else {
        $("hidden-signature_pages").value = ps.sigPages;
      }
    }

    if (previewMode === "watermark-text" || previewMode === "watermark-image") {
      $("hidden-rotation").value = ps.wmRotation.toString();
      $("hidden-opacity").value  = ps.wmOpacity.toString();
      const rotField = document.querySelector('input[name="rotation"]');
      const opField  = document.querySelector('input[name="opacity"]');
      if (rotField && !rotField.matches(':focus')) rotField.value = ps.wmRotation;
      if (opField  && !opField.matches(':focus'))  opField.value  = ps.wmOpacity;
    }
  }

  function updatePreviewHint() {
    const el = $("preview-hint");
    if (!el || !previewState) return;
    const ps = previewState;

    if (previewMode === "scissors") {
      const n = ps.splitPoints.size;
      el.textContent = n === 0
        ? "Click ✂ between pages to split there. No scissors = split every page."
        : `Will split into ${n + 1} parts at ${Array.from(ps.splitPoints).sort((a,b)=>a-b).join(", ")}.`;
    } else if (previewMode === "toggle-remove") {
      const n = ps.selected.size;
      el.textContent = n === 0 ? "Click pages to mark them for removal."
                               : `${n} page(s) will be removed.`;
    } else if (previewMode === "toggle-extract") {
      const n = ps.selected.size;
      el.textContent = n === 0 ? "Click pages to include them in the extracted PDF."
                               : `${n} page(s) will be extracted.`;
    } else if (previewMode === "rotate") {
      const n = Object.values(ps.rotations).filter((d) => d !== 0).length;
      el.textContent = n === 0 ? "Click each page to rotate it 90° clockwise."
                               : `${n} page(s) rotated.`;
    } else if (previewMode === "reorder") {
      el.textContent = ps.swapFirst === null
        ? "Click a page, then another, to swap them."
        : `Selected page ${ps.swapFirst}. Click another to swap.`;
    } else if (previewMode === "sign") {
      let where = "last page";
      if (ps.sigPages === "all") where = "every page";
      else if (ps.sigPages === "selected") where = `${ps.sigSelected.size} selected page(s)`;
      el.textContent = `Click anywhere on a page to place the signature, or use the ` +
        `arrow pad to nudge it. It will appear on ${where}.`;
    } else if (previewMode === "watermark-text") {
      el.textContent = `Watermark sits behind the page content (Word-style). ` +
        `Rotation ${Math.round(ps.wmRotation)}°.`;
    } else if (previewMode === "watermark-image") {
      el.textContent = `Image sits behind the page content. ` +
        `Rotation ${Math.round(ps.wmRotation)}°.`;
    }
  }

  // Live re-sync for text watermark
  const textFallback = document.querySelector('input[name="text"]');
  textFallback?.addEventListener("input", () => {
    if (previewMode === "watermark-text") renderPreviewStrip();
  });

  // Toolbar actions
  $("preview-back")?.addEventListener("click", () => show(stageUpload));
  $("preview-clear")?.addEventListener("click", () => {
    if (!previewState) return;
    previewState.splitPoints.clear();
    previewState.selected.clear();
    previewState.rotations = {};
    previewState.swapFirst = null;
    previewState.sigSelected.clear();
    if (previewMode === "sign") {
      previewState.sigX = 0.60;
      previewState.sigY = 0.75;
      updateSigPosLabel();
    }
    if (previewMode === "watermark-text" || previewMode === "watermark-image") {
      previewState.wmRotation = 45;
      previewState.wmOpacity  = 0.15;
      const r = $("wm-rotation"); if (r) r.value = 45;
      const o = $("wm-opacity");  if (o) o.value = 0.15;
      const rv = $("wm-rotation-val"); if (rv) rv.textContent = "45°";
      const ov = $("wm-opacity-val");  if (ov) ov.textContent = "15%";
    }
    if (previewMode === "sign") renderSigPageChips();
    renderPreviewStrip();
    updateHiddenFields();
    updatePreviewHint();
  });
  $("preview-select-all")?.addEventListener("click", () => {
    if (!previewState) return;
    if (previewMode === "toggle-remove" || previewMode === "toggle-extract") {
      for (let i = 1; i <= previewState.pageCount; i++) previewState.selected.add(i);
    } else if (previewMode === "rotate") {
      for (let i = 1; i <= previewState.pageCount; i++) previewState.rotations[i] = 90;
    } else if (previewMode === "sign" && previewState.sigPages === "selected") {
      for (let i = 1; i <= previewState.pageCount; i++) previewState.sigSelected.add(i);
      renderSigPageChips();
    }
    renderPreviewStrip();
    updateHiddenFields();
    updatePreviewHint();
  });

  // Lightbox
  const lightbox = $("lightbox");
  const lightboxImg = $("lightbox-img");
  $("lightbox-close")?.addEventListener("click", () => { lightbox.hidden = true; });
  lightbox?.addEventListener("click", (e) => { if (e.target === lightbox) lightbox.hidden = true; });
  function openLightbox(pageNum) {
    if (!previewState) return;
    lightboxImg.src = `/api/preview/page/${previewState.sessionId}/${pageNum}`;
    lightbox.hidden = false;
  }

  // Preview → Convert
  $("preview-run")?.addEventListener("click", () => runConversion(true));

  // ============================================================
  // CONVERSION
  // ============================================================
  async function runConversion(fromPreview = false) {
    if (progressFill) progressFill.style.width = "0%";
    if (statusText) statusText.textContent = "Uploading…";
    show(stageProgress);

    let pct = 0;
    const timer = setInterval(() => {
      pct = Math.min(pct + Math.random() * 10, 88);
      if (progressFill) progressFill.style.width = pct + "%";
    }, 180);

    try {
      const fd = new FormData();

      if (fromPreview && previewState) {
        fd.append("preview_session", previewState.sessionId);
        ["split_points", "rotations", "order", "pages",
         "signature_x", "signature_y", "signature_w", "signature_pages",
         "rotation", "opacity"].forEach((k) => {
          const el = $("hidden-" + k);
          if (el) fd.append(k, el.value);
        });
        const det = document.querySelector(".preview-options");
        if (det) {
          det.querySelectorAll("input, select, textarea").forEach((el) => {
            if (el.name) fd.append(el.name, el.value);
          });
        }
      } else {
        selectedFiles.forEach((f) => fd.append("files", f, f.name));
        if (stageOptions) {
          stageOptions.querySelectorAll("input, select, textarea").forEach((el) => {
            if (el.name) fd.append(el.name, el.value);
          });
        }
        if (urlInput && urlInput.value.trim()) fd.append("url", urlInput.value.trim());
      }

      const res = await fetch(`/api/run/${toolId}`, { method: "POST", body: fd });
      const data = await res.json().catch(() => ({}));

      clearInterval(timer);
      if (progressFill) progressFill.style.width = "100%";

      if (!res.ok) {
        errorText.textContent = data.error || `Server error (${res.status})`;
        setTimeout(() => show(stageError), 200);
        return;
      }

      download.href = data.download_url;
      download.setAttribute("download", data.filename || "");
      resultText.textContent = `Saved as "${data.filename}".`;
      setTimeout(() => show(stageResult), 240);
    } catch (err) {
      clearInterval(timer);
      errorText.textContent = err.message || "Network error.";
      show(stageError);
    }
  }

  runBtn?.addEventListener("click", () => runConversion(false));

  function humanSize(bytes) {
    if (!bytes) return "0 B";
    const k = 1024, s = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return (bytes / Math.pow(k, i)).toFixed(1) + " " + s[i];
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  updateNextState();
  show(stageUpload);
})();

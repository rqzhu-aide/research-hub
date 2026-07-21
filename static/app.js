(function () {
  "use strict";

  const dirtyForms = new Set();
  const guardedBaselines = new WeakMap();
  const draftStoragePrefix = "research-hub:form-draft:";
  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";
  let partialRequestActive = false;
  let projectRequestController = null;
  let projectRequestToken = 0;
  let progressRequestActive = false;
  let pollFailureCount = 0;
  let nextPollAt = 0;
  let sidebarReturnFocus = null;
  let currentProjectUrl = window.location.href;
  let allowNextUnload = false;
  let suppressNextPopstate = false;
  const mobileSidebarQuery = window.matchMedia("(max-width: 800px)");
  let historyIndex = Number.isInteger(window.history.state?.researchHubIndex)
    ? window.history.state.researchHubIndex
    : 0;
  window.history.replaceState(
    { ...(window.history.state || {}), researchHubIndex: historyIndex },
    "",
    window.location.href
  );

  function editableDraftControls(form) {
    return Array.from(form.elements).filter((control) =>
      control.matches("input, textarea, select") &&
      control.name && control.name !== "csrf_token" &&
      control.type !== "hidden" && !control.disabled && !control.readOnly &&
      !["submit", "button", "reset", "file"].includes(control.type)
    );
  }

  function serializedForm(form) {
    return JSON.stringify(editableDraftControls(form)
      .map((control) => [
        control.name,
        control.type,
        ["checkbox", "radio"].includes(control.type) ? control.checked : null,
        control.value
      ]));
  }

  function initializeGuardedForms(root = document) {
    root.querySelectorAll("form[data-unsaved-guard]").forEach((form) => {
      if (!guardedBaselines.has(form)) guardedBaselines.set(form, serializedForm(form));
    });
  }

  function updateDirtyForm(form) {
    if (!guardedBaselines.has(form)) guardedBaselines.set(form, serializedForm(form));
    if (serializedForm(form) === guardedBaselines.get(form)) dirtyForms.delete(form);
    else dirtyForms.add(form);
  }

  function hasDirtyFormWithin(root) {
    return Array.from(dirtyForms).some((form) => form.isConnected && root.contains(form));
  }

  function guardedFormSnapshot(root) {
    return new Map(Array.from(root.querySelectorAll("form[data-unsaved-guard]"))
      .map((form) => [form, serializedForm(form)]));
  }

  function guardedFormsChanged(root, snapshot) {
    const currentForms = Array.from(root.querySelectorAll("form[data-unsaved-guard]"));
    return currentForms.length !== snapshot.size || currentForms
      .some((form) => !snapshot.has(form) || serializedForm(form) !== snapshot.get(form));
  }

  function mutableProgressControl(target) {
    const active = document.activeElement;
    if (!(active instanceof Element) || !target.contains(active)) return null;
    return active.closest(
      "input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='reset']), " +
      "textarea, select, [contenteditable='true']"
    );
  }

  function progressFocusKey(target) {
    const active = document.activeElement;
    if (!(active instanceof Element) || !target.contains(active)) return "";
    return active.closest("[data-progress-focus]")?.dataset.progressFocus || "";
  }

  function restoreProgressFocus(root, key) {
    if (!key) return;
    const match = Array.from(root.querySelectorAll("[data-progress-focus]"))
      .find((element) => element.dataset.progressFocus === key);
    match?.focus({ preventScroll: true });
  }

  function openProgressDetails(root) {
    return new Set(Array.from(root.querySelectorAll("details[open][data-progress-details]"))
      .map((element) => element.dataset.progressDetails)
      .filter(Boolean));
  }

  function restoreProgressDetails(root, openKeys) {
    root.querySelectorAll("details[data-progress-details]").forEach((element) => {
      element.open = openKeys.has(element.dataset.progressDetails);
    });
  }

  function progressAnnouncement(root) {
    return root.querySelector("[data-progress-announcement]")?.textContent
      .replace(/\s+/g, " ").trim() || "";
  }

  function draftKey(form) {
    return form.dataset.draftKey
      ? `${draftStoragePrefix}${form.dataset.draftKey}`
      : null;
  }

  function persistDraft(form) {
    const key = draftKey(form);
    if (!key) return;
    const values = editableDraftControls(form)
      .filter((control) => control.type !== "radio" || control.checked)
      .map((control) => ({
        name: control.name,
        type: control.type,
        checked: ["checkbox", "radio"].includes(control.type) ? control.checked : null,
        value: control.value
      }));
    try {
      window.sessionStorage.setItem(key, JSON.stringify({
        path: window.location.pathname,
        savedAt: Date.now(),
        values
      }));
    } catch (_error) {
      // Form submission remains available when browser storage is disabled.
    }
  }

  function clearStoredDrafts() {
    try {
      Object.keys(window.sessionStorage)
        .filter((key) => key.startsWith(draftStoragePrefix))
        .forEach((key) => window.sessionStorage.removeItem(key));
    } catch (_error) {
      // No action is needed when browser storage is disabled.
    }
  }

  function restoreDraftsAfterError() {
    if (!document.querySelector(".flash-error")) {
      clearStoredDrafts();
      return;
    }
    document.querySelectorAll("form[data-unsaved-guard]").forEach((form) => {
      try {
        const key = draftKey(form);
        if (!key) return;
        const raw = window.sessionStorage.getItem(key);
        if (!raw) return;
        const draft = JSON.parse(raw);
        if (draft.path !== window.location.pathname || Date.now() - draft.savedAt > 30 * 60 * 1000) {
          window.sessionStorage.removeItem(key);
          return;
        }
        draft.values.forEach((item) => {
          const controls = Array.from(form.elements).filter((control) =>
            control.name === item.name && control.type !== "hidden"
          );
          if (item.type === "radio") {
            const selected = controls.find((control) =>
              control.type === "radio" && control.value === item.value
            );
            if (selected) selected.checked = true;
          } else if (item.type === "checkbox") {
            controls.filter((control) =>
              control.type === "checkbox" && control.value === item.value
            ).forEach((control) => { control.checked = Boolean(item.checked); });
          } else {
            const control = controls.find((candidate) => candidate.type === item.type);
            if (control) control.value = item.value;
          }
        });
        updateDirtyForm(form);
      } catch (_error) {
        const key = draftKey(form);
        if (key) window.sessionStorage.removeItem(key);
      }
    });
  }

  function formatTimes(root = document) {
    root.querySelectorAll("time[datetime]").forEach((node) => {
      const value = node.getAttribute("datetime");
      if (!value || node.dataset.localized === "true") return;
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return;
      node.textContent = new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium", timeStyle: "short"
      }).format(date);
      node.dataset.localized = "true";
    });
  }

  function announce(message) {
    const region = document.getElementById("interface-status");
    if (!region) return;
    region.textContent = "";
    window.requestAnimationFrame(() => { region.textContent = message; });
  }

  function clearAsyncError(anchor, key) {
    const scope = anchor?.parentElement || document;
    scope.querySelector(`[data-async-error="${key}"]`)?.remove();
  }

  function showAsyncError(anchor, key, message, retry, retryLabel = "Retry now") {
    if (!anchor) return;
    clearAsyncError(anchor, key);
    const error = document.createElement("div");
    error.className = "inline-error async-error";
    error.dataset.asyncError = key;
    error.setAttribute("role", "alert");
    const text = document.createElement("span");
    text.textContent = message;
    error.appendChild(text);
    if (retry) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn-sm";
      button.textContent = retryLabel;
      button.addEventListener("click", retry, { once: true });
      error.appendChild(button);
    }
    anchor.insertAdjacentElement("beforebegin", error);
  }

  function setSidebar(open) {
    const sidebar = document.getElementById("primary-sidebar");
    const workspace = document.querySelector(".workspace-shell");
    if (!sidebar) return;
    if (!mobileSidebarQuery.matches) {
      document.body.classList.remove("sidebar-open");
      sidebar.inert = false;
      sidebar.removeAttribute("aria-hidden");
      if (workspace) workspace.inert = false;
      document.querySelectorAll("[data-sidebar-open]").forEach((button) => {
        button.setAttribute("aria-expanded", "false");
      });
      sidebarReturnFocus = null;
      return;
    }
    if (open && !document.body.classList.contains("sidebar-open")) {
      sidebarReturnFocus = document.activeElement;
    }
    document.body.classList.toggle("sidebar-open", open);
    if (!open) {
      if (workspace) workspace.inert = false;
      if (sidebarReturnFocus instanceof HTMLElement && sidebarReturnFocus.isConnected) {
        sidebarReturnFocus.focus({ preventScroll: true });
      }
      sidebarReturnFocus = null;
      sidebar.inert = true;
      sidebar.setAttribute("aria-hidden", "true");
    } else {
      sidebar.inert = false;
      sidebar.setAttribute("aria-hidden", "false");
      if (workspace) workspace.inert = true;
    }
    document.querySelectorAll("[data-sidebar-open]").forEach((button) => {
      button.setAttribute("aria-expanded", String(open));
    });
    if (open) {
      window.requestAnimationFrame(() => {
        sidebar?.querySelector("[data-sidebar-close], a[href], button")?.focus();
      });
    }
  }

  function setDescriptionEditing(editing) {
    const view = document.querySelector("[data-description-view]");
    const form = document.querySelector("[data-description-form]");
    const edit = document.querySelector("[data-description-edit]");
    const save = document.querySelector("[data-description-save]");
    const cancel = document.querySelector("[data-description-cancel]");
    if (!view || !form || !edit || !save || !cancel) return;
    view.hidden = editing;
    form.hidden = !editing;
    edit.hidden = editing;
    save.hidden = !editing;
    cancel.hidden = !editing;
    if (editing) {
      const editor = form.querySelector("textarea");
      if (editor) {
        editor.dataset.initialValue = editor.value;
        editor.focus();
      }
    }
  }

  function discardDescriptionEdit() {
    const form = document.querySelector("[data-description-form]");
    const editor = form?.querySelector("textarea");
    if (editor && Object.prototype.hasOwnProperty.call(editor.dataset, "initialValue")) {
      editor.value = editor.dataset.initialValue;
    }
    if (form) {
      dirtyForms.delete(form);
      guardedBaselines.set(form, serializedForm(form));
    }
    setDescriptionEditing(false);
    document.querySelector("[data-description-edit]")?.focus({ preventScroll: true });
  }

  function requestDescriptionDiscard() {
    const form = document.querySelector("[data-description-form]");
    if (form && dirtyForms.has(form) &&
        !window.confirm("Discard the unsaved project brief changes?")) return;
    discardDescriptionEdit();
  }

  async function openFolder(button) {
    const status = document.getElementById("folder-action-status");
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    if (status) status.textContent = "Opening folder...";
    try {
      const body = new URLSearchParams({
        csrf_token: csrfToken(),
        project_identity: button.dataset.projectIdentity || ""
      });
      const response = await fetch(button.dataset.openFolderUrl, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
        body
      });
      if (!response.ok) throw new Error((await response.text()) || `Request failed (${response.status})`);
      if (status) status.textContent = "Folder opened.";
      announce("Project folder opened.");
    } catch (error) {
      if (status) status.textContent = `Could not open folder: ${error.message}`;
      announce("Could not open the project folder.");
    } finally {
      button.disabled = false;
      button.removeAttribute("aria-busy");
    }
  }

  function updateSlugPreview(value) {
    const slug = value.trim().toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "name";
    document.querySelectorAll(".slug-preview").forEach((node) => { node.textContent = slug; });
  }

  function updateTheoryPlan(input) {
    const control = input.closest("[data-theory-plan-control]");
    if (!control || !input.checked) return;
    const plan = input.closest(".fixed-plan-choice");
    const countLabel = plan?.querySelector("[data-stage-count]");
    const baseStageCount = Number.parseInt(
      countLabel?.dataset.baseStageCount || "3", 10
    );
    const count = input.value === "audit_only" ? 1
      : input.value === "standard_with_audit" ? baseStageCount + 1 : baseStageCount;
    if (countLabel) {
      countLabel.textContent = input.value === "audit_only"
        ? "1 fixed audit stage"
        : input.value === "standard_with_audit"
          ? `${count} fixed stages, including independent proof audit`
          : `${count} fixed theory stages`;
    }
    const phaseRoot = input.closest("#project-tabs") || document;
    const display = phaseRoot.querySelector("[data-theory-plan-display]");
    if (display) {
      const summary = display.querySelector("[data-theory-plan-summary]");
      if (summary) {
        summary.textContent = input.value === "audit_only"
          ? "Independent audit of one sealed existing theory artifact, 1 stage"
          : input.value === "standard_with_audit"
            ? `Standard theory plus independent proof audit, ${count} stages`
            : `Standard theory, ${count} stages`;
      }
      display.querySelectorAll("[data-theory-member]").forEach((member) => {
        const isReviewer = member.dataset.theoryMember === "paper_reviewer";
        member.hidden = input.value === "audit_only" ? !isReviewer
          : input.value === "standard" ? isReviewer : false;
      });
      display.querySelectorAll("[data-theory-standard-stage]").forEach((stage) => {
        stage.hidden = input.value === "audit_only";
      });
      const auditStage = display.querySelector("[data-theory-audit-stage]");
      if (auditStage) auditStage.hidden = input.value === "standard";
      const auditIndex = display.querySelector("[data-theory-audit-index]");
      if (auditIndex) {
        auditIndex.textContent = input.value === "audit_only"
          ? "1" : String(baseStageCount + 1);
      }
    }
    const sourceRow = control.querySelector("[data-theory-audit-source]");
    const scopeRow = control.querySelector("[data-theory-audit-scope]");
    const sourceSelect = sourceRow?.querySelector("select");
    const needsSource = input.value === "audit_only";
    if (sourceRow) sourceRow.hidden = !needsSource;
    if (scopeRow) scopeRow.hidden = !needsSource;
    if (sourceSelect) {
      sourceSelect.disabled = !needsSource;
      sourceSelect.required = needsSource;
    }
    const methodControl = input.closest("form")?.querySelector(
      "[data-method-selection-control]"
    );
    if (methodControl) {
      methodControl.querySelectorAll("input").forEach((field) => {
        field.disabled = needsSource;
      });
      methodControl.setAttribute("aria-disabled", needsSource ? "true" : "false");
    }
  }

  function initializeTheoryPlans(root = document) {
    root.querySelectorAll("[data-theory-plan]:checked").forEach(updateTheoryPlan);
  }

  async function loadProjectTabs(url, pushHistory) {
    const target = document.getElementById("project-tabs");
    if (!target) {
      window.location.assign(url);
      return;
    }
    const formSnapshot = guardedFormSnapshot(target);
    const focusAtRequestStart = document.activeElement;
    if (projectRequestController) projectRequestController.abort();
    const controller = new AbortController();
    const requestToken = ++projectRequestToken;
    projectRequestController = controller;
    partialRequestActive = true;
    target.setAttribute("aria-busy", "true");
    try {
      const response = await fetch(url, {
        headers: { "HX-Request": "true", "Accept": "text/html" },
        credentials: "same-origin",
        signal: controller.signal
      });
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      const markup = await response.text();
      if (requestToken !== projectRequestToken) return;
      const template = document.createElement("template");
      template.innerHTML = markup.trim();
      const replacement = template.content.firstElementChild;
      if (!replacement || replacement.id !== "project-tabs") {
        throw new Error("The server returned an invalid project panel");
      }
      const focusedNow = document.activeElement;
      const focusChangedWithinTarget = focusedNow instanceof Element &&
        target.contains(focusedNow) && focusedNow !== focusAtRequestStart;
      if (!target.isConnected || guardedFormsChanged(target, formSnapshot) ||
          focusChangedWithinTarget) {
        announce("The project view was not changed because you started interacting with it.");
        showAsyncError(
          target,
          "project-interaction",
          "The project view was not changed because you started editing or moved focus while it was loading. Choose the destination again when you are ready."
        );
        return;
      }
      dirtyForms.forEach((form) => {
        if (target.contains(form)) dirtyForms.delete(form);
      });
      target.replaceWith(replacement);
      if (pushHistory) {
        historyIndex += 1;
        window.history.pushState({ researchHubIndex: historyIndex }, "", url);
      }
      currentProjectUrl = window.location.href;
      formatTimes(replacement);
      initializeGuardedForms(replacement);
      initializeTheoryPlans(replacement);
      clearAsyncError(replacement, "project-tabs");
      clearAsyncError(replacement, "project-interaction");
      if (pushHistory) {
        replacement.querySelector(".tab[aria-current='page']")?.focus({ preventScroll: true });
      }
      announce("Project view updated.");
    } catch (error) {
      if (error.name === "AbortError" || requestToken !== projectRequestToken) return;
      announce(`The interface could not refresh. ${error.message}`);
      showAsyncError(
        target,
        "project-tabs",
        `The project view could not be refreshed. ${error.message}`,
        () => loadProjectTabs(url, pushHistory)
      );
    } finally {
      if (requestToken === projectRequestToken) {
        partialRequestActive = false;
        projectRequestController = null;
        document.getElementById("project-tabs")?.removeAttribute("aria-busy");
      }
    }
  }

  async function saveProfile(form) {
    if (form.dataset.saving === "true") return;
    form.dataset.saving = "true";
    form.classList.add("htmx-request");
    const controls = form.querySelectorAll("select, button");
    controls.forEach((control) => { control.disabled = true; });
    try {
      const response = await fetch(form.action, {
        method: "POST",
        headers: { "HX-Request": "true", "X-CSRF-Token": csrfToken() },
        body: new FormData(form),
        credentials: "same-origin"
      });
      if (!response.ok) throw new Error((await response.text()) || `Request failed (${response.status})`);
      const template = document.createElement("template");
      template.innerHTML = (await response.text()).trim();
      const replacement = template.content.firstElementChild;
      const card = form.closest(".profile-card");
      if (!replacement || !card || replacement.id !== card.id) {
        throw new Error("The server returned an invalid profile card");
      }
      clearAsyncError(form, "profile-save");
      card.replaceWith(replacement);
      replacement.querySelector("[data-profile-select]")?.focus({ preventScroll: true });
      announce("Agent profile saved for future runs.");
    } catch (error) {
      announce(`The profile could not be saved. ${error.message}`);
      showAsyncError(
        form,
        "profile-save",
        `The profile was not saved. ${error.message}`,
        () => saveProfile(form)
      );
      controls.forEach((control) => { control.disabled = false; });
      form.classList.remove("htmx-request");
      form.dataset.saving = "false";
    }
  }

  async function pollRunProgress(target) {
    if (progressRequestActive || mutableProgressControl(target) || hasDirtyFormWithin(target)) return;
    const url = target.dataset.runPollUrl;
    if (!url) return;
    const priorStatusSignature = target.dataset.progressStatusSignature || "";
    progressRequestActive = true;
    try {
      const response = await fetch(url, {
        headers: { "HX-Request": "true", "Accept": "text/html" },
        credentials: "same-origin"
      });
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      const template = document.createElement("template");
      template.innerHTML = (await response.text()).trim();
      const replacement = template.content.firstElementChild;
      if (!replacement || replacement.id !== "run-progress-region") {
        throw new Error("The server returned invalid run progress");
      }
      if (!target.isConnected || mutableProgressControl(target) || hasDirtyFormWithin(target)) return;
      const runStopped = replacement.dataset.runActive !== "true";
      const nextStatusSignature = replacement.dataset.progressStatusSignature || "";
      const nextAnnouncement = progressAnnouncement(replacement);
      const focusKey = progressFocusKey(target);
      const openDetails = openProgressDetails(target);
      clearAsyncError(target, "run-progress");
      target.replaceWith(replacement);
      formatTimes(replacement);
      initializeGuardedForms(replacement);
      restoreProgressDetails(replacement, openDetails);
      restoreProgressFocus(replacement, focusKey);
      pollFailureCount = 0;
      nextPollAt = 0;
      if (!runStopped && nextStatusSignature &&
          nextStatusSignature !== priorStatusSignature && nextAnnouncement) {
        announce(nextAnnouncement);
      }
      if (runStopped) {
        if (dirtyForms.size) {
          showAsyncError(
            replacement,
            "run-stopped-dirty",
            "The run stopped. Your unsaved input was kept. Refresh the result when you are ready.",
            () => {
              if (dirtyForms.size && !window.confirm(
                "Refresh the result and discard the unsaved changes?"
              )) return;
              loadProjectTabs(window.location.href, false);
            },
            "Refresh result"
          );
          announce("The run stopped. Unsaved input was kept.");
        } else {
          await loadProjectTabs(window.location.href, false);
          announce("The run stopped. Review its result and choose the next action.");
        }
      }
    } catch (error) {
      pollFailureCount += 1;
      nextPollAt = Date.now() + Math.min(30, 3 * (2 ** (pollFailureCount - 1))) * 1000;
      announce(`Run progress could not be refreshed. ${error.message}`);
      showAsyncError(
        target,
        "run-progress",
        `Live progress may be stale. ${error.message}`,
        () => {
          nextPollAt = 0;
          pollRunProgress(target);
        }
      );
    } finally {
      progressRequestActive = false;
    }
  }

  document.addEventListener("click", (event) => {
    const historyToggle = event.target.closest("[data-history-toggle]");
    if (historyToggle) {
      const table = document.getElementById(historyToggle.dataset.historyTarget || "");
      const olderRows = table?.querySelectorAll("[data-history-older-row]") || [];
      const expand = historyToggle.getAttribute("aria-expanded") !== "true";
      olderRows.forEach((row) => { row.hidden = !expand; });
      historyToggle.setAttribute("aria-expanded", String(expand));
      historyToggle.textContent = expand
        ? historyToggle.dataset.expandedLabel
        : historyToggle.dataset.collapsedLabel;
      return;
    }

    const open = event.target.closest("[data-sidebar-open]");
    if (open) { setSidebar(true); return; }

    const close = event.target.closest("[data-sidebar-close]");
    if (close) { setSidebar(false); return; }

    const edit = event.target.closest("[data-description-edit]");
    if (edit) { setDescriptionEditing(true); return; }

    const cancel = event.target.closest("[data-description-cancel]");
    if (cancel) { requestDescriptionDiscard(); return; }

    const folderButton = event.target.closest("[data-open-folder-url]");
    if (folderButton) { openFolder(folderButton); return; }

    const link = event.target.closest("a[href]");
    const plainCurrentWindowNavigation = link && event.button === 0 &&
      !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey &&
      (!link.target || link.target === "_self");
    if (plainCurrentWindowNavigation && dirtyForms.size &&
        !link.closest("[data-allow-dirty-navigation]")) {
      const samePageAnchor = link.hash && link.pathname === window.location.pathname && link.search === window.location.search;
      if (samePageAnchor) return;
      if (!window.confirm("You have unsaved changes. Leave without saving?")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        return;
      }
      if (!link.hasAttribute("hx-get")) allowNextUnload = true;
    }

    if (plainCurrentWindowNavigation && link.hasAttribute("hx-get") && !event.defaultPrevented &&
        event.button === 0 && !event.metaKey && !event.ctrlKey &&
        !event.shiftKey && !event.altKey) {
      const url = link.getAttribute("hx-get");
      if (url) {
        event.preventDefault();
        loadProjectTabs(url, link.getAttribute("hx-push-url") === "true");
      }
    }
  }, true);

  document.addEventListener("input", (event) => {
    const form = event.target.closest("form[data-unsaved-guard]");
    if (form) updateDirtyForm(form);
    if (event.target.matches("[data-project-name]")) updateSlugPreview(event.target.value);
  });

  document.addEventListener("change", (event) => {
    const form = event.target.closest("form[data-unsaved-guard]");
    if (form) updateDirtyForm(form);
    if (event.target.matches("[data-theory-plan]")) {
      updateTheoryPlan(event.target);
    }
  });

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (form.matches("[data-profile-form]")) {
      event.preventDefault();
      saveProfile(form);
      return;
    }
    const prompt = form.dataset.confirm;
    if (prompt && !window.confirm(prompt)) {
      event.preventDefault();
      return;
    }
    if (form.dataset.submitted === "true") {
      event.preventDefault();
      return;
    }
    if (form.matches("[data-unsaved-guard]")) persistDraft(form);
    form.dataset.submitted = "true";
    form.setAttribute("aria-busy", "true");
    form.querySelectorAll("button[type='submit'], input[type='submit']").forEach((control) => {
      control.disabled = true;
    });
    allowNextUnload = true;
  });

  window.addEventListener("beforeunload", (event) => {
    if (allowNextUnload) {
      allowNextUnload = false;
      return;
    }
    if (!dirtyForms.size) return;
    event.preventDefault();
    event.returnValue = "";
  });

  window.addEventListener("popstate", (event) => {
    if (suppressNextPopstate) {
      suppressNextPopstate = false;
      return;
    }
    const requestedUrl = window.location.href;
    const requestedIndex = Number.isInteger(event.state?.researchHubIndex)
      ? event.state.researchHubIndex
      : historyIndex;
    if (dirtyForms.size) {
      if (!window.confirm("You have unsaved changes. Leave without saving?")) {
        const delta = historyIndex - requestedIndex;
        if (delta) {
          suppressNextPopstate = true;
          window.history.go(delta);
        } else {
          window.history.replaceState(
            { ...(window.history.state || {}), researchHubIndex: historyIndex },
            "",
            currentProjectUrl
          );
        }
        return;
      }
    }
    historyIndex = requestedIndex;
    loadProjectTabs(requestedUrl, false);
  });

  window.addEventListener("pageshow", () => {
    initializeGuardedForms();
    initializeTheoryPlans();
  });

  window.setInterval(() => {
    if (document.hidden || partialRequestActive || progressRequestActive || Date.now() < nextPollAt) return;
    const progress = document.querySelector("#run-progress-region[data-run-poll-url]");
    if (progress) pollRunProgress(progress);
  }, 3000);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Tab" && document.body.classList.contains("sidebar-open")) {
      const sidebar = document.getElementById("primary-sidebar");
      const focusable = sidebar ? Array.from(sidebar.querySelectorAll(
        "a[href], button:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex='-1'])"
      )).filter((element) => element.getClientRects().length > 0 && !element.closest("[inert]")) : [];
      if (focusable.length) {
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault(); last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault(); first.focus();
        }
      }
    }
    if (event.key === "Escape") {
      if (document.body.classList.contains("sidebar-open")) setSidebar(false);
      if (document.querySelector("[data-description-form]:not([hidden])")) requestDescriptionDiscard();
    }
  });

  mobileSidebarQuery.addEventListener("change", () => setSidebar(false));
  setSidebar(false);
  initializeGuardedForms();
  restoreDraftsAfterError();
  initializeTheoryPlans();
  formatTimes();
})();

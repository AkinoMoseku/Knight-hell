const GUIDE_VERSION = 1;

function guidePageName() {
  const path = window.location.pathname;
  if (path === "/demo") return "demo";
  if (path === "/login") return "login";
  if (path === "/signup") return "signup";
  if (path === "/onboarding") return "onboarding";
  if (path === "/settings") return "settings";
  if (path === "/settings/ai") return "ai-settings";
  if (path === "/tasks/new") return "new-task";
  if (path === "/") return "dashboard";
  if (/^\/tasks\/[^/]+\/approval$/.test(path)) return "approval";
  if (/^\/tasks\/[^/]+\/execution$/.test(path)) return "execution";
  if (/^\/tasks\/[^/]+\/results$/.test(path)) return "results";
  if (/^\/tasks\/[^/]+$/.test(path)) return "task";
  return "other";
}

function guideStorageKey() {
  return `flowremote.guide.${document.body.dataset.userId || "guest"}.v${GUIDE_VERSION}`;
}

function guideDefaultState() {
  return { active: true, currentStep: null, dismissed: [] };
}

function guideLoadState() {
  try {
    return { ...guideDefaultState(), ...JSON.parse(localStorage.getItem(guideStorageKey()) || "{}") };
  } catch {
    return guideDefaultState();
  }
}

function guideSaveState(state) {
  localStorage.setItem(guideStorageKey(), JSON.stringify(state));
}

function guideStepMatches(step) {
  if (step.page !== guidePageName()) return false;
  if (!step.statuses) return true;
  return step.statuses.includes(document.body.dataset.taskStatus || "");
}

function guideTargetPath(step) {
  const taskId = document.body.dataset.taskId;
  const paths = {
    dashboard: "/",
    demo: "/demo",
    login: "/login",
    signup: "/signup",
    onboarding: "/onboarding",
    "new-task": "/tasks/new",
    settings: "/settings",
    approval: taskId ? `/tasks/${taskId}/approval` : "/",
    execution: taskId ? `/tasks/${taskId}/execution` : "/",
    results: taskId ? `/tasks/${taskId}/results` : "/",
  };
  return paths[step.nextPage] || null;
}

function guideResolveStep(state) {
  const steps = window.FLOWREMOTE_GUIDE || [];
  const saved = steps.find((step) => step.id === state.currentStep);
  if (saved && guideStepMatches(saved) && document.querySelector(`[data-guide-section="${saved.section}"]`)) {
    return saved;
  }
  return steps.find((step) => (
    guideStepMatches(step)
    && document.querySelector(`[data-guide-section="${step.section}"]`)
  )) || null;
}

function guideRemoveCard() {
  document.querySelector(".guide-card")?.remove();
  document.querySelectorAll(".guide-highlight").forEach((node) => {
    node.classList.remove("guide-highlight");
  });
}

function guideRenderToolbar(state, step) {
  let toolbar = document.querySelector(".guide-toolbar");
  if (!state.active) {
    toolbar?.remove();
    return;
  }
  if (!toolbar) {
    toolbar = document.createElement("div");
    toolbar.className = "guide-toolbar";
    toolbar.setAttribute("aria-label", "Guided tour controls");
    document.body.append(toolbar);
  }
  const steps = window.FLOWREMOTE_GUIDE || [];
  const index = step ? steps.findIndex((candidate) => candidate.id === step.id) + 1 : 0;
  toolbar.replaceChildren();
  const label = document.createElement("span");
  label.textContent = step ? `Guide ${index}/${steps.length}` : "Guide";
  const show = document.createElement("button");
  show.type = "button";
  show.textContent = "Show";
  show.addEventListener("click", () => guideShowCurrent(state));
  const exit = document.createElement("button");
  exit.type = "button";
  exit.className = "guide-exit";
  exit.textContent = "Exit";
  exit.addEventListener("click", () => {
    state.active = false;
    guideSaveState(state);
    guideRemoveCard();
    guideRenderToolbar(state, null);
  });
  toolbar.append(label, show, exit);
}

function guideNextButton(step, state) {
  if (!step.next) return null;
  const next = (window.FLOWREMOTE_GUIDE || []).find((candidate) => candidate.id === step.next);
  if (!next) return null;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "guide-primary";
  button.textContent = next.page === step.page ? "Next section" : "Next step";
  button.addEventListener("click", () => {
    state.currentStep = next.id;
    guideSaveState(state);
    if (next.page === step.page) {
      guideRender(state);
    } else {
      const path = guideTargetPath(step);
      if (path) window.location.assign(path);
    }
  });
  return button;
}

function guideRenderCard(step, state) {
  guideRemoveCard();
  const section = document.querySelector(`[data-guide-section="${step.section}"]`);
  if (!section) return;
  const steps = window.FLOWREMOTE_GUIDE || [];
  const index = steps.findIndex((candidate) => candidate.id === step.id) + 1;
  section.classList.add("guide-highlight");
  const card = document.createElement("aside");
  card.className = "guide-card";
  card.setAttribute("role", "region");
  card.dataset.guideId = step.id;
  const close = document.createElement("button");
  close.type = "button";
  close.className = "guide-close";
  close.setAttribute("aria-label", "Close this guide step");
  close.textContent = "×";
  close.addEventListener("click", () => {
    if (!state.dismissed.includes(step.id)) state.dismissed.push(step.id);
    guideSaveState(state);
    guideRemoveCard();
  });
  const progress = document.createElement("p");
  progress.className = "guide-progress";
  progress.textContent = `Step ${index} of ${steps.length}`;
  const title = document.createElement("h3");
  title.textContent = step.title;
  const body = document.createElement("p");
  body.textContent = step.body;
  const actions = document.createElement("div");
  actions.className = "guide-actions";
  const next = guideNextButton(step, state);
  if (next) {
    actions.append(next);
  } else {
    const done = document.createElement("button");
    done.type = "button";
    done.className = "guide-primary";
    done.textContent = "Got it";
    done.addEventListener("click", () => guideRemoveCard());
    actions.append(done);
  }
  card.append(close, progress, title, body, actions);
  section.append(card);
}

function guideShowCurrent(state) {
  const step = guideResolveStep(state);
  if (!step) return;
  state.currentStep = step.id;
  guideSaveState(state);
  guideRenderCard(step, state);
  guideRenderToolbar(state, step);
}

function guideRender(state) {
  if (!state.active) {
    guideRemoveCard();
    guideRenderToolbar(state, null);
    return;
  }
  const step = guideResolveStep(state);
  if (!step) {
    guideRemoveCard();
    guideRenderToolbar(state, null);
    return;
  }
  state.currentStep = step.id;
  guideSaveState(state);
  if (state.dismissed.includes(step.id)) {
    guideRemoveCard();
  } else {
    guideRenderCard(step, state);
  }
  guideRenderToolbar(state, step);
}

let guideState = guideLoadState();
if (new URLSearchParams(window.location.search).get("guide") === "start") {
  guideState = guideDefaultState();
  guideSaveState(guideState);
}

document.getElementById("guide-start")?.addEventListener("click", () => {
  guideState.active = true;
  guideState.dismissed = [];
  guideRender(guideState);
});

window.addEventListener("DOMContentLoaded", () => guideRender(guideState));

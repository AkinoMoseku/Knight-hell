window.FLOWREMOTE_GUIDE = [
  {
    id: "demo-welcome",
    page: "demo",
    section: "demo-welcome",
    title: "Start the FlowRemote demo",
    body: "Create a new account to walk through registration and AI-RPA setup, or use the quick operator login for the seeded task.",
    next: "account-register",
    nextPage: "signup"
  },
  {
    id: "account-login",
    page: "login",
    section: "account-login",
    title: "Welcome to FlowRemote",
    body: "Sign in to restore your server-side work state. A new user can create an account and configure AI and RPA first.",
    next: "account-register"
  },
  {
    id: "account-register",
    page: "signup",
    section: "account-register",
    title: "Create your account",
    body: "Registration stores your account on the FlowRemote server. After signup, you will configure which AI and RPA targets this user may use.",
    next: "onboarding-ai",
    nextPage: "onboarding"
  },
  {
    id: "onboarding-ai",
    page: "onboarding",
    section: "onboarding-ai",
    title: "Choose AI assistance",
    body: "Demo AI works offline and needs no key. AI only recommends corrections; it cannot approve or execute a task.",
    next: "onboarding-rpa"
  },
  {
    id: "onboarding-rpa",
    page: "onboarding",
    section: "onboarding-rpa",
    title: "Choose RPA targets and limits",
    body: "Select the local Excel and HTTP targets, then set daily limits. Human approval remains permanently required.",
    next: "dashboard-overview",
    nextPage: "dashboard"
  },
  {
    id: "dashboard-overview",
    page: "dashboard",
    section: "dashboard-overview",
    title: "Your AI-RPA workspace",
    body: "The dashboard is the control center for tasks, AI and RPA. Start a new task to demonstrate the full workflow.",
    next: "task-create",
    nextPage: "new-task"
  },
  {
    id: "task-create",
    page: "new-task",
    section: "task-create",
    title: "Create a task",
    body: "Give this task a name, then choose an Excel workbook. The task belongs only to the signed-in account.",
    next: "task-upload"
  },
  {
    id: "task-upload",
    page: "new-task",
    section: "task-upload",
    title: "Upload the source workbook",
    body: "Use the bundled demo workbook for a predictable demo. FlowRemote checks headers, duplicate IDs, numbers, dates and totals.",
    next: null
  },
  {
    id: "task-wait",
    page: "task",
    statuses: ["ready", "validating"],
    section: "validation-summary",
    title: "Validation stage",
    body: "The source file is saved. Validation produces real passed and flagged records from the workbook.",
    next: null
  },
  {
    id: "task-review",
    page: "task",
    statuses: ["review_required"],
    section: "exception-review",
    title: "Review exceptions with AI",
    body: "Generate a suggestion, inspect its evidence and confidence, then Accept, Edit or Skip. Every decision is attributed to a human.",
    next: "approval-gate"
  },
  {
    id: "approval-gate",
    page: "task",
    statuses: ["review_required"],
    section: "approval-gate",
    title: "Human approval gate",
    body: "Approval unlocks only when every exception is resolved. AI cannot bypass this gate.",
    next: null
  },
  {
    id: "task-pending",
    page: "task",
    statuses: ["pending_approval"],
    section: "approval-gate",
    title: "Ready for approval",
    body: "Open the approval page to review the exact record count that will be released to RPA execution.",
    next: "approval-summary",
    nextPage: "approval"
  },
  {
    id: "approval-summary",
    page: "approval",
    section: "approval-summary",
    title: "Review the release snapshot",
    body: "Check input, skipped and ready counts. Nothing is written before the explicit approval action.",
    next: "approval-action"
  },
  {
    id: "approval-action",
    page: "approval",
    section: "approval-action",
    title: "Release approved records",
    body: "Approve & Execute records a single approval and starts one execution attempt.",
    next: null
  },
  {
    id: "execution-progress",
    page: "execution",
    section: "execution-progress",
    title: "Watch execution",
    body: "Execution advances in visible record batches and records progress in the server database.",
    next: "result-summary",
    nextPage: "results"
  },
  {
    id: "result-summary",
    page: "results",
    section: "result-summary",
    title: "Review execution results",
    body: "Results show written, synced, skipped, duration and success rate. The current targets are clearly labelled as simulated.",
    next: "audit-log"
  },
  {
    id: "audit-log",
    page: "results",
    section: "audit-log",
    title: "Inspect the audit trail",
    body: "Decisions, approval and execution are append-only events. The JSON export provides the same evidence outside the demo database.",
    next: "settings-ai",
    nextPage: "settings"
  },
  {
    id: "settings-ai",
    page: "settings",
    section: "settings-ai",
    title: "Manage AI usage",
    body: "Review the active model, endpoint, encrypted key state and daily request limit.",
    next: "settings-rpa"
  },
  {
    id: "settings-rpa",
    page: "settings",
    section: "settings-rpa",
    title: "Manage RPA usage",
    body: "Enable or disable AI and RPA, select local targets and set usage limits. Approval cannot be disabled.",
    next: null
  }
];

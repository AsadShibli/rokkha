export const en = {
  brand: { tagline: "Public-safety dispatch" },
  nav: {
    how: "How it works",
    features: "Features",
    roles: "Roles",
    apiDocs: "API docs",
    tryDemo: "Try the demo",
    signIn: "Sign in",
    signOut: "Sign out",
  },
  hero: {
    eyebrow: "SOS dispatch · Live tracking · Online GD",
    titleStart: "Help, dispatched in",
    titleAccent: "seconds.",
    body: "Press SOS and Rokkha finds the nearest available officer, assigns them instantly, and lets you watch help arrive. File a General Diary online, in Bangla or English, with an AI-drafted form.",
    primary: "Try the live demo",
    secondary: "Explore the API",
    cardStatus: "Officer assigned",
    cardDistance: "0.4 km away · arriving",
    cardOfficer: "Sub-Inspector Tanvir Hasan",
    chipEscalation: "Auto-escalates if not accepted in 2 min",
    chipGd: "GD DHA-GUL-2026-000001 approved",
  },
  stats: [
    { value: "1", label: "transaction to lock the nearest officer" },
    { value: "2 min", label: "before an unaccepted SOS moves on" },
    { value: "4", label: "roles, one platform" },
    { value: "2", label: "languages for AI GD drafts" },
  ],
  how: {
    title: "From SOS to safe, in three steps",
    steps: [
      {
        title: "Press and hold SOS",
        body: "Your location goes out once. A second open SOS is blocked, so one person can't tie up several officers.",
      },
      {
        title: "The nearest officer is locked in",
        body: "Distance is computed in the database and the officer row is locked, so two calls at once never get the same officer.",
      },
      {
        title: "Watch help arrive",
        body: "Status changes and the officer's position stream to your screen live. Every step is kept as an audit trail.",
      },
    ],
  },
  features: {
    title: "Built for the moments that matter",
    items: [
      { title: "Smart dispatch", body: "City-wide nearest-officer search with no double booking." },
      { title: "Live tracking", body: "WebSocket updates for status and officer location." },
      { title: "Auto-escalation", body: "Not accepted in time? It moves to the next nearest officer." },
      { title: "Online GD", body: "Numbered per station and year, reviewed by the station admin." },
      { title: "AI drafting", body: "Describe what happened in Bangla or English; get a ready form." },
      { title: "Station dashboard", body: "Queues, officers on duty and response times at a glance." },
    ],
  },
  roles: {
    title: "One platform, four views",
    body: "Each role sees only what it needs. Pick one to explore the demo.",
    items: {
      citizen: { name: "Citizen", body: "Raise SOS, track help, file and follow GDs." },
      officer: { name: "Officer", body: "Go on duty, share location, accept and resolve." },
      station_admin: { name: "Station admin", body: "Run the queue, reassign, review GDs." },
      super_admin: { name: "Control room", body: "Stations, admins and city-wide numbers." },
    },
  },
  cta: { title: "See it working end to end", body: "One click signs you in with seeded demo data.", button: "Open the demo" },
  footer: {
    note: "A portfolio project: FastAPI, PostgreSQL, Redis and Next.js. Not affiliated with any agency.",
    source: "Source on GitHub",
  },
  login: {
    title: "Welcome back",
    subtitle: "Sign in with your phone number.",
    phone: "Phone",
    password: "Password",
    submit: "Sign in",
    submitting: "Signing in…",
    noAccount: "New here?",
    register: "Create a citizen account",
    demoTitle: "Or try the demo as",
    demoHint: "Seeded accounts, password rokkha1234",
    panelTitle: "Every second counts.",
    panelBody: "Rokkha connects citizens, officers and stations so help moves as fast as the request.",
    coldStart: "Waking the server (free hosting)… this can take up to a minute.",
  },
  register: {
    title: "Create your account",
    subtitle: "Citizens can raise SOS and file GDs.",
    name: "Full name",
    email: "Email (optional)",
    submit: "Create account",
    submitting: "Creating…",
    haveAccount: "Already registered?",
    signIn: "Sign in",
  },
  app: {
    welcome: "Welcome back",
    roleLabels: {
      citizen: "Citizen",
      officer: "Officer",
      station_admin: "Station admin",
      super_admin: "Control room",
    },
    loading: "Loading…",
  },
  errors: {
    generic: "Something went wrong. Please try again.",
  },
};

export type Dictionary = typeof en;

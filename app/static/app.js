// Matchday: a small front end for the Football Stats API. No framework, no build step.

const state = { leagues: [], teams: new Map(), token: localStorage.getItem("token"), me: null };

const ROUND_NAMES = {
  PLAYOFFS: "Knockout play-offs", LAST_16: "Round of 16", QUARTER_FINALS: "Quarter-finals",
  SEMI_FINALS: "Semi-finals", FINAL: "Final",
};
const ROUND_POINTS = { PLAYOFFS: 1, LAST_16: 2, QUARTER_FINALS: 4, SEMI_FINALS: 8, FINAL: 16 };
const EXAMPLE_QUESTIONS = [
  "What is the ruling on DOGSO?",
  "How long can a goalkeeper hold the ball?",
  "Can you be offside from a throw-in?",
  "What counts as serious foul play?",
  "How does a penalty shoot-out work?",
];

// ---------- helpers ----------

const $ = (selector) => document.querySelector(selector);

// Everything that comes from the API goes through esc() before it touches innerHTML.
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.json);
  }
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401 && state.token) signOut();
  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    throw new Error(Array.isArray(detail) ? detail.map((d) => d.msg).join(", ") : detail || `Request failed (${response.status})`);
  }
  return body;
}

function crest(teamId, label) {
  const team = state.teams.get(teamId);
  if (team?.crest_url) return `<img class="crest" src="${esc(team.crest_url)}" alt="" loading="lazy" referrerpolicy="no-referrer">`;
  return `<span class="crest-fallback">${esc(team?.short_name || label || "?")}</span>`;
}

const teamName = (id) => state.teams.get(id)?.name ?? "Unknown";
const skeleton = (rows = 6) => `<div class="card pad">${'<div class="skeleton"></div>'.repeat(rows)}</div>`;
const empty = (title, text = "") => `<div class="empty"><strong>${esc(title)}</strong>${text}</div>`;
const fail = (error) => empty("Something went wrong", esc(error.message));

const dayFormat = new Intl.DateTimeFormat(undefined, { weekday: "long", day: "numeric", month: "long" });
const timeFormat = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });
const shortDate = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

function segmented(container, items, activeId, onSelect) {
  container.innerHTML = items
    .map((item) => `<button data-id="${esc(item.id)}" class="${item.id === activeId ? "active" : ""}">${esc(item.label)}</button>`)
    .join("");
  container.onclick = (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    container.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === button));
    onSelect(button.dataset.id);
  };
}

async function latestSeasons(leagueId) {
  const seasons = await api(`/leagues/${leagueId}/seasons`);
  return seasons.reverse(); // newest first
}

const championsLeague = () => state.leagues.find((l) => l.name.includes("Champions League"));
const shortLeagueName = (name) => ({ "Primera Division": "La Liga", "UEFA Champions League": "Champions League" }[name] || name);

// ---------- tables ----------

const tables = { leagueId: null, seasonId: null };

async function showTables() {
  if (!state.leagues.length) return ($("#tables-body").innerHTML = empty("No leagues yet", "Run <code>python -m app.sync PL</code> to load data."));
  tables.leagueId ??= state.leagues[0].id;
  segmented($("#tables-leagues"), state.leagues.map((l) => ({ id: String(l.id), label: shortLeagueName(l.name) })), String(tables.leagueId),
    (id) => { tables.leagueId = Number(id); tables.seasonId = null; showTables(); });

  const seasons = await latestSeasons(tables.leagueId);
  tables.seasonId ??= seasons[0]?.id;
  const select = $("#tables-season");
  select.innerHTML = seasons.map((s) => `<option value="${s.id}" ${s.id === tables.seasonId ? "selected" : ""}>${esc(s.name)}</option>`).join("");
  select.onchange = () => { tables.seasonId = Number(select.value); renderTable(); };
  renderTable();
}

function zonesFor(leagueName, rowCount) {
  if (leagueName.includes("Champions League")) {
    return { legend: [["var(--green)", "Round of 16"], ["var(--accent)", "Knockout play-offs"]],
             colour: (pos) => (pos <= 8 ? "var(--green)" : pos <= 24 ? "var(--accent)" : null) };
  }
  return { legend: [["var(--accent)", "Champions League"], ["var(--red)", "Relegation"]],
           colour: (pos) => (pos <= 4 ? "var(--accent)" : pos > rowCount - 3 && rowCount >= 18 ? "var(--red)" : null) };
}

async function renderTable() {
  const body = $("#tables-body");
  body.innerHTML = skeleton(10);
  try {
    const params = tables.seasonId ? `?season_id=${tables.seasonId}` : "";
    const rows = await api(`/leagues/${tables.leagueId}/standings${params}`);
    const league = state.leagues.find((l) => l.id === tables.leagueId);
    const zones = zonesFor(league.name, rows.length);
    $("#tables-legend").innerHTML = zones.legend.map(([c, label]) => `<span style="--c:${c}">${label}</span>`).join("");
    if (!rows.length) return (body.innerHTML = empty("No table yet"));
    body.innerHTML = `
      <table>
        <thead><tr><th></th><th class="team">Club</th><th>P</th><th class="hide-sm">W</th><th class="hide-sm">D</th>
          <th class="hide-sm">L</th><th class="hide-sm">GF</th><th class="hide-sm">GA</th><th>GD</th><th>Pts</th></tr></thead>
        <tbody>${rows.map((r) => `
          <tr>
            <td class="pos" style="--zone:${zones.colour(r.position) || "transparent"}">${r.position}</td>
            <td class="team"><div class="team-cell">${crest(r.team_id)}<span>${esc(r.team_name)}</span></div></td>
            <td>${r.played}</td><td class="hide-sm">${r.won}</td><td class="hide-sm">${r.drawn}</td><td class="hide-sm">${r.lost}</td>
            <td class="hide-sm muted">${r.goals_for}</td><td class="hide-sm muted">${r.goals_against}</td>
            <td class="muted">${r.goal_difference > 0 ? "+" : ""}${r.goal_difference}</td><td class="pts">${r.points}</td>
          </tr>`).join("")}
        </tbody>
      </table>`;
  } catch (error) {
    body.innerHTML = fail(error);
  }
}

// ---------- fixtures ----------

const fixtures = { leagueId: null, mode: "upcoming" };

async function showFixtures() {
  if (!state.leagues.length) return;
  fixtures.leagueId ??= state.leagues[0].id;
  segmented($("#fixtures-leagues"), state.leagues.map((l) => ({ id: String(l.id), label: shortLeagueName(l.name) })), String(fixtures.leagueId),
    (id) => { fixtures.leagueId = Number(id); renderFixtures(); });
  $("#fixtures-mode").onclick = (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    $("#fixtures-mode").querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === button));
    fixtures.mode = button.dataset.mode;
    renderFixtures();
  };
  renderFixtures();
}

function matchRow(m) {
  const finished = m.status === "finished";
  const live = m.status === "live";
  const homeWon = finished && m.home_score > m.away_score;
  const awayWon = finished && m.away_score > m.home_score;
  let middle;
  if (finished || live) {
    middle = `<div class="score">${m.home_score} – ${m.away_score}</div>${live ? '<span class="badge live">Live</span>' : ""}`;
  } else if (m.status === "postponed") {
    middle = '<span class="badge ppd">Postponed</span>';
  } else {
    middle = `<div class="time">${timeFormat.format(new Date(m.kickoff))}</div>`;
  }
  return `
    <div class="match">
      <div class="home ${homeWon ? "winner" : awayWon ? "loser" : ""}"><span>${esc(teamName(m.home_team_id))}</span>${crest(m.home_team_id)}</div>
      <div class="mid">${middle}</div>
      <div class="away ${awayWon ? "winner" : homeWon ? "loser" : ""}">${crest(m.away_team_id)}<span>${esc(teamName(m.away_team_id))}</span></div>
    </div>`;
}

async function renderFixtures() {
  const body = $("#fixtures-body");
  body.innerHTML = skeleton(8);
  try {
    const [season] = await latestSeasons(fixtures.leagueId);
    const all = await api(`/matches?league_id=${fixtures.leagueId}${season ? `&season_id=${season.id}` : ""}`);
    const recent = Date.now() - 3 * 3600 * 1000;
    const matches = fixtures.mode === "upcoming"
      ? all.filter((m) => m.status !== "finished" && new Date(m.kickoff) >= recent).slice(0, 40)
      : all.filter((m) => m.status === "finished").reverse().slice(0, 40);
    if (!matches.length) return (body.innerHTML = `<div class="card">${empty(fixtures.mode === "upcoming" ? "No upcoming matches" : "No results yet")}</div>`);

    const days = new Map();
    for (const m of matches) {
      const day = dayFormat.format(new Date(m.kickoff));
      days.set(day, [...(days.get(day) || []), m]);
    }
    body.innerHTML = [...days].map(([day, list]) => `
      <div class="day"><h3 class="day-title">${esc(day)}</h3><div class="card">${list.map(matchRow).join("")}</div></div>`).join("");
  } catch (error) {
    body.innerHTML = fail(error);
  }
}

// ---------- bracket ----------

const bracket = { seasonId: null, mode: "real", seasons: [] };

async function showBracket() {
  const cl = championsLeague();
  if (!cl) return ($("#bracket-body").innerHTML = empty("No Champions League data", "Run <code>python -m app.sync CL</code>."));
  const seasons = await latestSeasons(cl.id);
  bracket.seasons = seasons;
  const params = new URLSearchParams(location.hash.split("?")[1]);  // e.g. #bracket?season=5&mode=projected
  if (params.get("season")) bracket.seasonId = Number(params.get("season"));
  if (params.get("mode")) bracket.mode = params.get("mode");
  bracket.seasonId ??= seasons[0]?.id;
  const select = $("#bracket-season");
  select.innerHTML = seasons.map((s) => `<option value="${s.id}" ${s.id === bracket.seasonId ? "selected" : ""}>${esc(s.name)}</option>`).join("");
  select.onchange = () => { bracket.seasonId = Number(select.value); renderBracket(); };
  $("#bracket-mode").onclick = (event) => {
    const button = event.target.closest("button");
    if (button) setBracketMode(button.dataset.mode);
  };
  setBracketMode(bracket.mode);
}

function setBracketMode(mode) {
  bracket.mode = mode;
  $("#bracket-mode").querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
  renderBracket();
}

function tieSide(side, tie, index) {
  if (!side.team_id) return `<div class="tie-side tbd">${esc(side.label)}</div>`;
  const won = tie.winner_team_id === side.team_id;
  const lost = tie.winner_team_id && !won;
  const agg = tie.aggregate ? tie.aggregate[index] : "";
  const seed = side.label && bracket.mode === "projected" ? `<span class="muted">${esc(side.label)}</span>` : "";
  return `<div class="tie-side ${won ? "won" : lost ? "lost" : ""}">${crest(side.team_id)}<span class="name">${esc(side.team_name)}</span>${seed}<span class="agg">${agg}</span></div>`;
}

function tieCard(tie, round) {
  const legs = tie.legs.map((leg) => {
    if (leg.status === "scheduled") return shortDate.format(new Date(leg.kickoff));
    const pens = leg.home_penalties !== null ? ` (${leg.home_penalties}–${leg.away_penalties} pens)` : "";
    return `${leg.home_score}–${leg.away_score}${pens}`;
  });
  const champion = round === "FINAL" && tie.winner_team_id ? `<div class="champion">🏆 ${esc(teamName(tie.winner_team_id))}</div>` : "";
  return `<div class="tie">${tieSide(tie.side_a, tie, 0)}${tieSide(tie.side_b, tie, 1)}
    ${legs.length ? `<div class="tie-legs">${legs.map(esc).join(" · ")}</div>` : ""}${champion}</div>`;
}

async function renderBracket() {
  const body = $("#bracket-body");
  body.innerHTML = skeleton(6);
  try {
    const path = `/seasons/${bracket.seasonId}/bracket${bracket.mode === "projected" ? "/projected" : ""}`;
    const data = await api(path);
    $("#bracket-subtitle").textContent = bracket.mode === "projected"
      ? "Who would meet if the league phase ended today, following UEFA's seeding."
      : "The knockout bracket, from the play-offs to the final.";
    if (!data.rounds.length) {
      const lastSeason = bracket.seasons.find((s) => s.id !== bracket.seasonId);
      body.innerHTML = `<div class="card">${empty("The knockouts haven't started yet",
        `<p>They begin in February.</p><button class="link" id="see-projected">See who would meet if it ended today →</button>
         ${lastSeason ? `<button class="link" id="see-last">See the ${esc(lastSeason.name)} bracket →</button>` : ""}`)}</div>`;
      $("#see-projected").onclick = () => setBracketMode("projected");
      if (lastSeason) $("#see-last").onclick = () => {
        bracket.seasonId = lastSeason.id;
        $("#bracket-season").value = lastSeason.id;
        setBracketMode("real");
      };
      return;
    }
    body.innerHTML = data.rounds.map((r) => `
      <div class="round ${r.round === "FINAL" ? "final" : ""}">
        <div class="round-title">${ROUND_NAMES[r.round] || esc(r.round)}</div>
        <div class="round-ties">${r.ties.map((t) => tieCard(t, r.round)).join("")}</div>
      </div>`).join("");
  } catch (error) {
    body.innerHTML = `<div class="card">${fail(error)}</div>`;
  }
}

// ---------- predictor ----------

async function showPredictor() {
  const cl = championsLeague();
  const body = $("#predictor-body");
  if (!cl) return (body.innerHTML = empty("No Champions League data"));
  const [season] = await latestSeasons(cl.id);
  renderLeaderboard(season.id);

  if (!state.token) {
    body.innerHTML = empty("Sign in to make your picks",
      `<p>Correct picks score ${Object.values(ROUND_POINTS).join(", ")} points from the play-offs to the final.</p>
       <button class="primary" id="predictor-signin">Sign in or create an account</button>`);
    $("#predictor-signin").onclick = () => openAuth("signin");
    return;
  }

  body.innerHTML = skeleton(5);
  try {
    const [data, mine] = await Promise.all([api(`/seasons/${season.id}/bracket`), api(`/seasons/${season.id}/predictions/me`)]);
    const key = (round, a, b) => `${round}:${Math.min(a, b)}:${Math.max(a, b)}`;
    const picks = new Map(mine.map((p) => [key(p.round, p.team_a_id, p.team_b_id), p]));
    const now = Date.now();
    const open = data.rounds.flatMap((r) => r.ties.map((t) => ({ ...t, round: r.round })))
      .filter((t) => t.legs[0].status === "scheduled" && new Date(t.legs[0].kickoff) > now);

    const openHtml = open.length
      ? open.map((t) => {
          const pick = picks.get(key(t.round, t.side_a.team_id, t.side_b.team_id));
          const option = (side) => `
            <button class="pick ${pick?.winner_team_id === side.team_id ? "chosen" : ""}"
              data-round="${t.round}" data-a="${t.side_a.team_id}" data-b="${t.side_b.team_id}" data-winner="${side.team_id}">
              ${crest(side.team_id)}<span>${esc(side.team_name)}</span></button>`;
          return `<div class="pick-tie"><div class="pick-meta">${ROUND_NAMES[t.round]} · ${ROUND_POINTS[t.round]} pts · first leg ${shortDate.format(new Date(t.legs[0].kickoff))}</div>
            <div class="pick-options">${option(t.side_a)}${option(t.side_b)}</div></div>`;
        }).join("")
      : empty("No ties open for picks right now", "Picks open once knockout fixtures are set. Each tie locks at its first kick-off.");

    const history = mine.length
      ? `<h2 style="margin-top:28px">Your picks</h2>${mine.map((p) => `
          <div class="leader"><span class="rank">${p.correct === null ? "·" : p.correct ? "✓" : "✗"}</span>
            <span class="who">${esc(teamName(p.winner_team_id))} <span class="muted">· ${ROUND_NAMES[p.round]}</span></span>
            <span class="pts">${p.correct === null ? "" : `${p.points} pts`}</span></div>`).join("")}`
      : "";
    body.innerHTML = `<h2>Open ties</h2>${openHtml}${history}`;

    body.querySelectorAll(".pick").forEach((button) => (button.onclick = async () => {
      button.disabled = true;
      try {
        await api(`/seasons/${season.id}/predictions`, { method: "PUT", json: {
          round: button.dataset.round, team_a_id: Number(button.dataset.a),
          team_b_id: Number(button.dataset.b), winner_team_id: Number(button.dataset.winner) } });
        showPredictor();
      } catch (error) {
        alert(error.message);
        button.disabled = false;
      }
    }));
  } catch (error) {
    body.innerHTML = fail(error);
  }
}

async function renderLeaderboard(seasonId) {
  const board = $("#leaderboard");
  try {
    const rows = await api(`/seasons/${seasonId}/predictions/leaderboard`);
    board.innerHTML = rows.length
      ? rows.slice(0, 20).map((r) => `
          <div class="leader ${r.username === state.me?.username ? "me" : ""}">
            <span class="rank">${r.position}</span><span class="who">${esc(r.username)}</span>
            <span class="muted">${r.correct}/${r.predictions}</span><span class="pts">${r.points}</span></div>`).join("")
      : `<p class="muted">No predictions yet. Be the first.</p>`;
  } catch (error) {
    board.innerHTML = fail(error);
  }
}

// ---------- ask the rules ----------

function showRules() {
  $("#ask-examples").innerHTML = EXAMPLE_QUESTIONS.map((q) => `<button class="chip" type="button">${esc(q)}</button>`).join("");
  $("#ask-examples").onclick = (event) => {
    if (!event.target.matches(".chip")) return;
    $("#ask-input").value = event.target.textContent;
    ask();
  };
  $("#ask-form").onsubmit = (event) => { event.preventDefault(); ask(); };
  const question = new URLSearchParams(location.hash.split("?")[1]).get("q");  // e.g. #rules?q=What+is+offside
  if (question && question !== $("#ask-input").value) {
    $("#ask-input").value = question;
    ask();
  }
}

async function ask() {
  const question = $("#ask-input").value.trim();
  const result = $("#ask-result");
  if (question.length < 5) return;
  const button = $("#ask-form button");
  button.disabled = true;
  result.innerHTML = skeleton(4);
  try {
    const data = await api("/rules/ask", { method: "POST", json: { question } });
    // Turn the answer's [1] citations into links to the matching source below.
    const answer = data.answer
      ? esc(data.answer).replace(/\[(\d+)\]/g, (_, n) => `<sup><a href="#source-${n}" data-source="${n}">${n}</a></sup>`)
      : null;
    result.innerHTML = `
      ${data.note ? `<div class="note">${esc(data.note)}</div>` : ""}
      ${answer ? `<div class="card pad"><div class="answer">${answer}</div>
        <div class="answered-by">Written by ${esc(data.answered_by)} from the sources below. Always check the quoted Law.</div></div>` : ""}
      <div class="sources">${data.sources.map((s, i) => `
        <details class="source" id="source-${s.number}" ${i === 0 ? "open" : ""}>
          <summary><span class="cite">${s.number}</span>${esc(s.citation)}</summary><p>${esc(s.content)}</p>
        </details>`).join("")}</div>`;
    result.querySelectorAll("[data-source]").forEach((link) => (link.onclick = (event) => {
      event.preventDefault();
      const source = $(`#source-${link.dataset.source}`);
      source.open = true;
      source.classList.add("highlight");
      source.scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(() => source.classList.remove("highlight"), 1500);
    }));
  } catch (error) {
    result.innerHTML = `<div class="card">${fail(error)}</div>`;
  } finally {
    button.disabled = false;
  }
}

// ---------- accounts ----------

let authMode = "signin";

function openAuth(mode) {
  authMode = mode;
  const signin = mode === "signin";
  $("#auth-title").textContent = signin ? "Sign in" : "Create an account";
  $("#auth-submit").textContent = signin ? "Sign in" : "Create account";
  $("#auth-switch").textContent = signin ? "New here? Create an account" : "Already have an account? Sign in";
  $("#auth-form").password.autocomplete = signin ? "current-password" : "new-password";
  $("#auth-error").hidden = true;
  $("#auth-dialog").showModal();
}

async function submitAuth(event) {
  event.preventDefault();
  const form = $("#auth-form");
  const username = form.username.value.trim();
  const password = form.password.value;
  try {
    if (authMode === "register") await api("/auth/register", { method: "POST", json: { username, password } });
    const token = await api("/auth/login", { method: "POST", body: new URLSearchParams({ username, password }) });
    state.token = token.access_token;
    localStorage.setItem("token", state.token);
    $("#auth-dialog").close();
    form.reset();
    await loadMe();
    route();
  } catch (error) {
    $("#auth-error").textContent = error.message;
    $("#auth-error").hidden = false;
  }
}

function signOut() {
  state.token = null;
  state.me = null;
  localStorage.removeItem("token");
  renderAccount();
}

async function loadMe() {
  state.me = state.token ? await api("/auth/me").catch(() => null) : null;
  renderAccount();
}

function renderAccount() {
  const account = $("#account");
  if (state.me) {
    account.innerHTML = `<span>${esc(state.me.username)}</span><button class="secondary" id="sign-out">Sign out</button>`;
    $("#sign-out").onclick = () => { signOut(); route(); };
  } else {
    account.innerHTML = `<button class="secondary" id="sign-in">Sign in</button>`;
    $("#sign-in").onclick = () => openAuth("signin");
  }
}

// ---------- routing ----------

const VIEWS = { tables: showTables, fixtures: showFixtures, bracket: showBracket, predictor: showPredictor, rules: showRules };

function route() {
  const name = location.hash.slice(1).split("?")[0];
  const tab = VIEWS[name] ? name : "tables";
  document.querySelectorAll(".view").forEach((v) => (v.hidden = v.id !== `view-${tab}`));
  document.querySelectorAll("[data-tab]").forEach((a) => a.classList.toggle("active", a.dataset.tab === tab));
  VIEWS[tab]();
}

async function init() {
  $("#auth-form").onsubmit = submitAuth;
  $("#auth-switch").onclick = () => openAuth(authMode === "signin" ? "register" : "signin");
  $("#auth-close").onclick = () => $("#auth-dialog").close();
  window.addEventListener("hashchange", route);

  const [leagues, teams] = await Promise.all([api("/leagues"), api("/teams"), loadMe()]);
  const order = ["Premier League", "Primera Division", "UEFA Champions League"];
  state.leagues = leagues.sort((a, b) => (order.indexOf(a.name) + 1 || 99) - (order.indexOf(b.name) + 1 || 99));
  teams.forEach((t) => state.teams.set(t.id, t));
  route();
}

init();

// Shared by both rooms: requests, the speech loop, the interviewer's voice, the camera, and the report renderer.
const $ = id => document.getElementById(id);
const post = (u, b) => fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b || {}) }).then(r => r.json());
const show = id => document.querySelectorAll(".screen").forEach(s => s.classList.toggle("on", s.id === id));
const mmss = s => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const stamp = d => { const p = n => String(n).padStart(2, "0"); return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}`; };

/* Voice in. The browser's built-in speech recognition (Chrome and Edge) fills a text box.
   After `silence` ms with no new words, whatever is in the box is sent. Typing pauses that. */
function Listener({ box, interim, bar, silence = 3000, canSend, onSend, onHeard }) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rec = null, sendT = null, typing = false;
  const self = { on: true, paused: false, supported: !!SR, active: false };
  function drawBar(on) {
    bar.style.transition = "none"; bar.style.width = "0";
    if (on) { bar.offsetWidth; bar.style.transition = `width ${silence}ms linear`; bar.style.width = "100%"; }
  }
  self.arm = () => {
    clearTimeout(sendT); drawBar(true);
    sendT = setTimeout(() => { if (!typing && canSend()) self.send(); else if (!typing) self.arm(); }, silence);
  };
  self.send = () => {
    const t = box.value.trim(); drawBar(false);
    if (!t) return;
    box.value = ""; interim.textContent = ""; typing = false;
    onSend(t);
  };
  self.start = () => {
    if (!SR || !self.on || self.paused || rec || !self.active) return;
    rec = new SR(); rec.continuous = true; rec.interimResults = true; rec.lang = "en-US";
    rec.onresult = e => {
      let partial = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) box.value = (box.value.trim() + " " + r[0].transcript.trim()).trim();
        else partial += r[0].transcript;
      }
      interim.textContent = partial;
      onHeard && onHeard();
      clearTimeout(sendT); drawBar(false);
      if (!partial) self.arm();
    };
    rec.onerror = e => { if (e.error === "not-allowed") { self.on = false; self.onMuted && self.onMuted(); } };
    rec.onend = () => { rec = null; setTimeout(self.start, 200); };
    try { rec.start(); } catch (e) { rec = null; }
  };
  self.stop = () => { if (rec) { const r = rec; rec = null; r.onend = null; try { r.abort(); } catch (e) {} } };
  self.reset = () => { clearTimeout(sendT); drawBar(false); };
  self.pending = () => box.value.trim() && !typing;
  box.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); typing = false; clearTimeout(sendT); if (canSend()) self.send(); }
    else typing = true;
  });
  return self;
}

/* Voice out. Uses the system's text-to-speech voices; on Windows the "Natural" voices sound best. */
const Voice = {
  voice: null,
  pick(prefer) {
    const vs = speechSynthesis.getVoices().filter(v => v.lang.startsWith("en"));
    this.voice = vs.find(v => prefer.test(v.name) && /Natural/.test(v.name)) || vs.find(v => /Natural/.test(v.name))
      || vs.find(v => v.name === "Google US English") || vs.find(v => v.lang === "en-US") || vs[0] || null;
    return this.voice;
  },
  speak(text, { onStart, onEnd } = {}) {
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    if (this.voice) u.voice = this.voice;
    u.rate = 1.05;
    onStart && onStart();
    let done = false;
    const end = () => { if (!done) { done = true; onEnd && onEnd(); } };
    u.onend = end; u.onerror = end;
    // Some voices never fire onend; give up after a generous estimate.
    setTimeout(end, 2500 + text.length * 90);
    speechSynthesis.speak(u);
  },
};

async function startCamera(video, tile) {
  if (video.srcObject) return true;
  try {
    video.srcObject = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    tile && tile.classList.add("live");
    return true;
  } catch (e) { return false; }
}

const FILLERS = ["like", "um", "uh", "you know", "kind of", "sort of", "basically", "i guess", "honestly", "literally", "actually", "so yeah", "i mean"];
function deliveryStats(answers, startAt) {
  const words = answers.join(" ").toLowerCase().split(/\s+/).filter(Boolean);
  const text = " " + words.join(" ") + " ";
  const fillers = FILLERS.map(f => [f, (text.match(new RegExp("\\b" + f + "\\b", "g")) || []).length]).filter(x => x[1]).sort((a, b) => b[1] - a[1]);
  const lens = answers.map(t => t.split(/\s+/).length);
  return { turns: answers.length, words: words.length, longest: Math.max(0, ...lens), avg: lens.length ? Math.round(words.length / lens.length) : 0,
    fillers, fillerTotal: fillers.reduce((a, b) => a + b[1], 0), minutes: ((Date.now() - startAt) / 60000).toFixed(1) };
}

function statTiles(items) {
  return `<div class="stats">${items.map(([v, k]) => `<div class="stat"><b>${esc(v)}</b><span>${esc(k)}</span></div>`).join("")}</div>`;
}

/* A small markdown renderer for the report: headings, bullets, bold, code, and quotes. */
function md(s) {
  const inline = t => esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>");
  let html = "", list = false, code = false, buf = [];
  for (const raw of s.split("\n")) {
    if (raw.trim().startsWith("```")) {
      if (code) { html += `<pre>${esc(buf.join("\n"))}</pre>`; buf = []; }
      code = !code; continue;
    }
    if (code) { buf.push(raw); continue; }
    const l = raw.trim();
    if (!/^[-*] /.test(l) && list) { html += "</ul>"; list = false; }
    if (!l) continue;
    if (l.startsWith("### ")) html += `<h3>${inline(l.slice(4))}</h3>`;
    else if (l.startsWith("## ")) html += `<h2>${inline(l.slice(3))}</h2>`;
    else if (l.startsWith("# ")) html += `<h2>${inline(l.slice(2))}</h2>`;
    else if (/^[-*] /.test(l)) { if (!list) { html += "<ul>"; list = true; } html += `<li>${inline(l.slice(2))}</li>`; }
    else if (l.startsWith(">")) {
      const t = l.replace(/^>\s?/, ""), said = /^said:/i.test(t);
      html += `<blockquote class="${said ? "said" : ""}">${inline(said ? "You said: " + t.replace(/^said:\s*/i, "") : t)}</blockquote>`;
    } else html += `<p>${inline(l)}</p>`;
  }
  return html + (list ? "</ul>" : "");
}

function splitReport(text) {
  const sm = text.match(/SCORE:\s*([\d.]+)/), vm = text.match(/VERDICT:\s*(.+)/);
  return { score: sm ? parseFloat(sm[1]) : null, verdict: vm ? vm[1].trim() : "",
    body: text.replace(/^.*SCORE:.*$/m, "").replace(/^.*VERDICT:.*$/m, "").trim() };
}

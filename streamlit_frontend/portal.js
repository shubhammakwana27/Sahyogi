"use strict";
(() => {
  const frame = document.getElementById("portal");
  let revision = null, busy = false, downloaded = null;
  const send = (type, data = {}) => window.parent.postMessage({isStreamlitMessage: true, type, ...data}, "*");
  function size() {
    let height;
    try { height = window.parent.innerHeight; } catch (_) { height = window.screen.availHeight || 800; }
    height = Math.max(500, height);
    document.documentElement.style.height = height + "px";
    frame.style.height = height + "px";
    send("streamlit:setFrameHeight", {height});
  }
  function submit(method, path, data = {}) {
    if (busy) return;
    busy = true;
    frame.setAttribute("aria-busy", "true");
    send("streamlit:setComponentValue", {dataType:"json", value:{
      id: crypto.randomUUID(), revision, method, path, data,
    }});
  }
  frame.addEventListener("load", () => {
    const doc = frame.contentDocument;
    if (!doc) return;
    doc.addEventListener("submit", event => {
      event.preventDefault();
      const form = event.target;
      if (!form.checkValidity()) { form.reportValidity(); return; }
      const entries = new FormData(form);
      if (event.submitter && event.submitter.name) entries.append(event.submitter.name, event.submitter.value);
      const path = form.getAttribute("action") || "/";
      const method = (form.getAttribute("method") || "GET").toUpperCase();
      if (method === "GET") {
        const parts = path.split("?");
        const query = new URLSearchParams(parts[1] || "");
        for (const [key, value] of entries) query.append(key, value);
        submit("GET", parts[0] + "?" + query.toString());
      } else {
        submit("POST", path, Object.fromEntries(entries));
      }
    });
    doc.addEventListener("click", event => {
      const anchor = event.target.closest("a[href]");
      if (!anchor) return;
      const href = anchor.getAttribute("href");
      if (!href || href.startsWith("#")) return;
      if (href.startsWith("/") && !href.startsWith("//")) {
        event.preventDefault(); submit("GET", href);
      }
    });
    size();
  });
  window.addEventListener("message", event => {
    if (event.source !== window.parent || event.data.type !== "streamlit:render") return;
    const args = event.data.args;
    if (args.revision !== revision) {
      revision = args.revision;
      busy = false;
      frame.removeAttribute("aria-busy");
      // srcdoc uses the server's exact original page. No content is rewritten.
      frame.srcdoc = args.html;
    }
    const download = args.download;
    if (download && download.id !== downloaded) {
      downloaded = download.id;
      const bytes = Uint8Array.from(atob(download.content), ch => ch.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], {type:download.type}));
      const a = document.createElement("a");
      a.href = url; a.download = download.filename; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    }
    size();
  });
  window.addEventListener("resize", size);
  send("streamlit:componentReady", {apiVersion:1});
  size();
})();

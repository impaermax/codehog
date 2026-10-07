// Python syntax highlighting (requirement 2.6).
//
// Hand-written rather than a CDN library: the project has no build step, and
// pulling 40 KB of third-party code for one language on one screen is not worth
// it. The app also keeps working offline.
//
// How it works: a highlighted <pre> sits UNDER a transparent textarea and mirrors
// its content and scroll position. Typing, selection, the caret and browser
// autocomplete stay native, and the .editor selector used by lesson.js is unchanged.
(() => {
  const KEYWORDS = new Set([
    "and", "as", "assert", "async", "await", "break", "class", "continue", "def", "del",
    "elif", "else", "except", "finally", "for", "from", "global", "if", "import", "in",
    "is", "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try", "while",
    "with", "yield", "True", "False", "None", "match", "case",
  ]);

  const BUILTINS = new Set([
    "abs", "all", "any", "bool", "dict", "dir", "enumerate", "filter", "float", "format",
    "frozenset", "getattr", "hasattr", "input", "int", "isinstance", "len", "list", "map",
    "max", "min", "next", "open", "ord", "chr", "print", "range", "repr", "reversed", "round",
    "set", "setattr", "sorted", "str", "sum", "tuple", "type", "zip", "self",
  ]);

  const escapeHtml = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

  // Order matters: first the tokens whose contents must not be highlighted.
  const TOKEN = new RegExp([
    /#[^\n]*/,                                   // comment
    /"""[\s\S]*?"""|'''[\s\S]*?'''/,             // triple-quoted string
    /"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'/,   // string
    /\b\d+\.?\d*(?:[eE][+-]?\d+)?\b/,            // number
    /\b[A-Za-z_]\w*\b/,                          // word
  ].map((pattern) => pattern.source).join("|"), "g");

  function tokenClass(token, nextChar) {
    if (token[0] === "#") return "tok-com";
    if (token[0] === '"' || token[0] === "'") return "tok-str";
    if (/^\d/.test(token)) return "tok-num";
    if (KEYWORDS.has(token)) return "tok-kw";
    if (BUILTINS.has(token)) return "tok-builtin";
    if (nextChar === "(") return "tok-fn";
    return "";
  }

  function highlight(code) {
    let html = "";
    let position = 0;
    let match;
    TOKEN.lastIndex = 0;
    while ((match = TOKEN.exec(code)) !== null) {
      html += escapeHtml(code.slice(position, match.index));
      const token = match[0];
      position = match.index + token.length;
      const cls = tokenClass(token, code[position]);
      html += cls ? `<span class="${cls}">${escapeHtml(token)}</span>` : escapeHtml(token);
    }
    html += escapeHtml(code.slice(position));
    // A trailing newline is required, otherwise the last line gets "eaten"
    return html + "\n";
  }

  document.querySelectorAll("textarea.editor").forEach((textarea) => {
    if (textarea.closest(".editor-wrap")) return;

    const wrap = document.createElement("div");
    wrap.className = "editor-wrap";
    textarea.parentNode.insertBefore(wrap, textarea);

    const layer = document.createElement("pre");
    layer.className = "highlight";
    layer.setAttribute("aria-hidden", "true");
    wrap.append(layer, textarea);

    const render = () => { layer.innerHTML = highlight(textarea.value); };
    const syncScroll = () => {
      layer.scrollTop = textarea.scrollTop;
      layer.scrollLeft = textarea.scrollLeft;
    };

    textarea.addEventListener("input", () => { render(); syncScroll(); });
    textarea.addEventListener("scroll", syncScroll);

    // Tab inside the editor indents instead of moving focus.
    // Esc restores the default, so keyboard users are never trapped.
    let releaseTab = false;
    textarea.addEventListener("keydown", (event) => {
      if (event.key === "Escape") { releaseTab = true; return; }
      if (event.key !== "Tab" || releaseTab) { releaseTab = false; return; }
      event.preventDefault();
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      textarea.value = textarea.value.slice(0, start) + "    " + textarea.value.slice(end);
      textarea.selectionStart = textarea.selectionEnd = start + 4;
      render();
    });

    render();
  });
})();

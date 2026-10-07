// On mobile the showcase items are shown one at a time: three side by side do not fit.
(() => {
  const showcase = document.getElementById("showcase");
  if (!showcase) return;
  const items = [...showcase.querySelectorAll(".showcase-item")];
  if (items.length < 2) return;

  const dots = document.createElement("div");
  dots.className = "dots";
  items.forEach(() => dots.appendChild(document.createElement("i")));
  showcase.after(dots);

  let current = 0;
  const isMobile = () => window.matchMedia("(max-width: 860px)").matches;

  function show(index) {
    current = (index + items.length) % items.length;
    items.forEach((item, i) => item.classList.toggle("active", i === current));
    [...dots.children].forEach((dot, i) => dot.classList.toggle("active", i === current));
  }

  show(0);
  setInterval(() => { if (isMobile()) show(current + 1); }, 4200);
  dots.onclick = (event) => {
    const index = [...dots.children].indexOf(event.target);
    if (index >= 0) show(index);
  };
})();

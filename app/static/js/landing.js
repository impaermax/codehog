// На мобильном показываем ступени по очереди: три видео рядом там не помещаются.
(() => {
  const витрина = document.getElementById("витрина");
  if (!витрина) return;
  const ступени = [...витрина.querySelectorAll(".ступень")];
  if (ступени.length < 2) return;

  const точки = document.createElement("div");
  точки.className = "точки";
  ступени.forEach(() => точки.appendChild(document.createElement("i")));
  витрина.after(точки);

  let текущая = 0;
  const мобильный = () => window.matchMedia("(max-width: 860px)").matches;

  function показать(индекс) {
    текущая = (индекс + ступени.length) % ступени.length;
    ступени.forEach((э, i) => э.classList.toggle("активна", i === текущая));
    [...точки.children].forEach((т, i) => т.classList.toggle("активна", i === текущая));
    const видео = ступени[текущая].querySelector("video");
    if (видео && видео.paused) видео.play().catch(() => {});
  }

  показать(0);
  setInterval(() => { if (мобильный()) показать(текущая + 1); }, 4200);
  точки.onclick = (e) => {
    const i = [...точки.children].indexOf(e.target);
    if (i >= 0) показать(i);
  };
})();

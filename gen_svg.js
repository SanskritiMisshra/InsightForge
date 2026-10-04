const rects = [
    { width: 15, height: 20, y: 110, hoverHeight: 20, hoverY: 130, x: 40, fill: "rgba(255,255,255,0.15)", hoverFill: "var(--ac-sec)" },
    { width: 15, height: 20, y: 90, hoverHeight: 20, hoverY: 130, x: 60, fill: "var(--ac-main)", hoverFill: "var(--ac-main)" },
    { width: 15, height: 40, y: 70, hoverHeight: 30, hoverY: 120, x: 80, fill: "var(--ac-main)", hoverFill: "var(--ac-main)" },
    { width: 15, height: 30, y: 80, hoverHeight: 50, hoverY: 100, x: 100, fill: "var(--ac-main)", hoverFill: "var(--ac-main)" },
    { width: 15, height: 30, y: 110, hoverHeight: 40, hoverY: 110, x: 120, fill: "rgba(255,255,255,0.15)", hoverFill: "var(--ac-sec)" },
    { width: 15, height: 50, y: 110, hoverHeight: 20, hoverY: 130, x: 140, fill: "rgba(255,255,255,0.15)", hoverFill: "var(--ac-sec)" },
    { width: 15, height: 50, y: 60, hoverHeight: 30, hoverY: 120, x: 160, fill: "var(--ac-main)", hoverFill: "var(--ac-main)" },
    { width: 15, height: 30, y: 80, hoverHeight: 20, hoverY: 130, x: 180, fill: "var(--ac-main)", hoverFill: "var(--ac-main)" },
    { width: 15, height: 20, y: 110, hoverHeight: 40, hoverY: 110, x: 200, fill: "rgba(255,255,255,0.15)", hoverFill: "var(--ac-sec)" },
    { width: 15, height: 40, y: 70, hoverHeight: 60, hoverY: 90, x: 220, fill: "var(--ac-main)", hoverFill: "var(--ac-main)" },
    { width: 15, height: 30, y: 110, hoverHeight: 70, hoverY: 80, x: 240, fill: "rgba(255,255,255,0.15)", hoverFill: "var(--ac-sec)" },
    { width: 15, height: 50, y: 110, hoverHeight: 50, hoverY: 100, x: 260, fill: "rgba(255,255,255,0.15)", hoverFill: "var(--ac-sec)" },
    { width: 15, height: 20, y: 110, hoverHeight: 80, hoverY: 70, x: 280, fill: "rgba(255,255,255,0.15)", hoverFill: "var(--ac-sec)" },
    { width: 15, height: 30, y: 80, hoverHeight: 90, hoverY: 60, x: 300, fill: "var(--ac-main)", hoverFill: "var(--ac-main)" }
];

let html = "";
rects.forEach(r => {
    html += <rect width="" x="" class="ac-rect" rx="2" ry="2" style="--h: px; --y: px; --hh: px; --hy: px; --f: ; --hf: ;"></rect>\n;
});
console.log(html);

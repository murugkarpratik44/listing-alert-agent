"""Render a frame-driven HTML stage (window.render(t), window.DURATION) to numbered PNG frames."""
import asyncio, sys, os
from playwright.async_api import async_playwright
async def main(html, outdir, fps, w, h, scale, only=None):
    os.makedirs(outdir, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
        await pg.goto("file://" + os.path.abspath(html.split("?")[0]) + ("?" + html.split("?")[1] if "?" in html else ""))
        await pg.evaluate("document.fonts.ready")
        await pg.wait_for_timeout(800)
        dur = await pg.evaluate("window.DURATION")
        times = [float(x) for x in only.split(",")] if only else [i / fps for i in range(int(dur * fps))]
        for i, t in enumerate(times):
            await pg.evaluate(f"window.render({t})")
            await pg.screenshot(path=f"{outdir}/f{i:05d}.png")
        await b.close()
        print(len(times), "frames")
a = sys.argv
asyncio.run(main(a[1], a[2], float(a[3]), int(a[4]), int(a[5]), float(a[6]), a[7] if len(a) > 7 else None))

import urllib.request, time
import common as K
import config as C

def score(nodes):
    sc = 0
    for n in nodes:
        if (n.get("desc_md") or "").strip(): sc += 10
        sc += len(n.get("resources") or [])
        sc += score(n.get("children") or [])
    return sc

def dl(url, target):
    last = None
    for a in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r, open(target, "wb") as out:
                out.write(r.read())
            return
        except Exception as e:
            last = e
            try:
                if target.exists() and target.stat().st_size == 0: target.unlink()
            except Exception: pass
            time.sleep(3 * (a + 1))
    raise last

def run():
    print("=== SAVE EXTRAS (mo ta + resources) ===")
    chapters = K.load_best(C.META_PATTERN, score)
    if not chapters: print("Khong co meta_*.json -> bo qua\n"); return
    desc_n = fdl = fskip = lnk = fail = miss = 0
    for ct, f, course in chapters:
        chap = K.find_chapter_folder(ct)
        if chap is None: print(f"[!] khong khop folder '{ct}'\n"); continue
        lessons = K.walk(course.get("children") or [], chap)
        print(f"[{chap.name}] {len(lessons)} bai")
        for folder, node in lessons:
            try:
                if not folder.exists(): miss += 1; continue
                dm = (node.get("desc_md") or "").strip()
                if dm: (folder / "description.md").write_text(dm, encoding="utf-8"); desc_n += 1
                res = node.get("resources") or []
                links = [r for r in res if r.get("type") == "link"]
                fres  = [r for r in res if r.get("type") != "link" and r.get("url")]
                if links or fres:
                    rdir = folder / "resources"; rdir.mkdir(exist_ok=True)
                    if links:
                        (rdir / "_links.txt").write_text(
                            "\n".join(f"- {r.get('file_name','link')}: {r['url']}" for r in links),
                            encoding="utf-8"); lnk += len(links)
                    for r in fres:
                        tgt = rdir / K.san_file(r.get("file_name"))
                        if tgt.exists() and tgt.stat().st_size > 0: fskip += 1; continue
                        try: dl(r["url"], tgt); fdl += 1; print(f"   [file] {tgt.name}")
                        except Exception as e: fail += 1; print(f"   [LOI] {tgt.name}: {e}")
            except Exception as e:
                fail += 1; print(f"   [BO QUA] {folder.name}: {e}")
        print()
    print(f"--- EXTRAS: desc={desc_n} file={fdl} skip={fskip} link={lnk} loi={fail} thieu={miss} ---\n")
    if fail: print("Co loi tai resource -> link ky het han 8h: dump lai meta roi chay lai.\n")
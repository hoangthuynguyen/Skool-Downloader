import common as K
import config as C

def count_urls(nodes):
    c = 0
    for n in nodes:
        if n.get("url"): c += 1
        c += count_urls(n.get("children") or [])
    return c

def merged(folder):
    for ext in C.VIDEXT:
        p = folder / ("video" + ext)
        try:
            if p.exists() and p.stat().st_size > 0: return p
        except OSError: pass
    return None

def has_partial(folder):
    if not folder.exists(): return False
    for p in folder.glob("video.*"):
        if p.stem != "video" or p.suffix.lower() == ".part": return True
    return False

def run():
    print("=== AUDIT VIDEO ===")
    chapters = K.load_best(C.VID_PATTERN, count_urls)
    if not chapters: print("Khong co vid_*.json\n"); return
    done = []; part = []; miss = []; nofold = []; expected = set(); total = 0
    for ct, f, course in chapters:
        chap = K.find_chapter_folder(ct)
        for folder, node in K.walk(course.get("children") or [], chap or C.ROOT):
            if not node.get("url"): continue
            total += 1
            if chap is None: nofold.append(f"{ct} > {node.get('title','')}"); continue
            expected.add(str(folder).lower())
            rel = str(folder).replace(str(C.ROOT) + "\\", "")
            if merged(folder): done.append(rel)
            elif has_partial(folder): part.append(rel)
            else: miss.append(rel)
    orphan = []; gb = 0.0
    if C.ROOT.exists():
        for ext in C.VIDEXT:
            for p in C.ROOT.rglob(f"video{ext}"):
                if p.stem != "video" or any(x.lower() == "resources" for x in p.parts): continue
                try: gb += p.stat().st_size / (1024**3)
                except OSError: pass
                if str(p.parent).lower() not in expected:
                    orphan.append(str(p).replace(str(C.ROOT) + "\\", ""))
    pct = round(len(done) * 100 / total, 1) if total else 0
    out = ["===== AUDIT VIDEO =====",
           f"Tong bai co link: {total}",
           f"  DONE={len(done)}  PARTIAL={len(part)}  MISSING={len(miss)}  NOFOLDER={len(nofold)}  ORPHAN={len(orphan)}",
           f"  Dung luong: {gb:.1f} GB",
           f"  HOAN THANH: {len(done)}/{total} = {pct}%"]
    print("\n".join(out))
    detail = out + [""]
    for nm, items in [("PARTIAL", part), ("MISSING", miss), ("NOFOLDER", nofold), ("ORPHAN", orphan)]:
        detail.append(f"----- {nm} ({len(items)}) -----"); detail += ["  " + x for x in items]; detail.append("")
    report = C.ROOT / "video_audit.txt"
    report.write_text("\n".join(detail), encoding="utf-8")
    print(f">> Chi tiet: {report}\n")
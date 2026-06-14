"""Tao cay thu muc tu JSON dump: MOI BAI = 1 FOLDER (chua video + transcript + resources).
   Tu tao ca folder CHUONG neu khoa moi chua co (danh so theo _chapters.json / Chap<N>.json,
   hoac noi tiep so chuong lon nhat dang co)."""
import common as K
import config as C

def count_all(nodes):
    return sum(1 + count_all(n.get("children") or []) for n in nodes)

def run():
    print("=== TAO FOLDER ===")
    # meta_ co them desc/resources; vid_ chi co link -> dung cai nao co
    chapters = K.load_best(C.META_PATTERN, count_all) or K.load_best(C.VID_PATTERN, count_all)
    if not chapters:
        print("Khong co meta_*.json / vid_*.json -> bo qua\n"); return
    order = K.load_chapter_order()
    made_ch = made = 0
    for ct, f, course in chapters:
        chap, created = K.ensure_chapter_folder(ct, order)
        if created:
            made_ch += 1; print(f"  [chuong moi] {chap.name}")
        for folder, _ in K.walk(course.get("children") or [], chap):
            if not folder.exists():
                folder.mkdir(parents=True, exist_ok=True); made += 1
    print(f"Chuong tao moi: {made_ch} | folder bai tao moi: {made}\n")
